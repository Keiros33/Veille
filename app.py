import os, hashlib, time, threading, logging, re, json
from datetime import datetime
from urllib.request import urlopen, Request
from html.parser import HTMLParser
import psycopg2, psycopg2.extras
from pptx import Presentation
import io, base64 as b64mod
from flask import Flask, jsonify, request
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)
app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ.get('DATABASE_URL', '')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

SOURCES = [
    # Europe en Régions
    {"name": "Europe Nouvelle-Aquitaine", "cat": "Europe en Régions", "region": "Nouvelle-Aquitaine", "url": "https://www.europe-en-nouvelle-aquitaine.eu/fr/appels-a-projets.html"},
    {"name": "Europe Occitanie", "cat": "Europe en Régions", "region": "Occitanie", "url": "https://www.europe-en-occitanie.eu/"},
    {"name": "Europe PACA", "cat": "Europe en Régions", "region": "PACA", "url": "https://europe.maregionsud.fr/aides-et-appels-a-projets/projets"},
    {"name": "Europe AURA", "cat": "Europe en Régions", "region": "AURA", "url": "https://www.europeenauvergnerhonealpes.fr/aides-europeennes"},
    {"name": "Europe Bourgogne-FC", "cat": "Europe en Régions", "region": "Bourgogne-FC", "url": "https://www.europe-bfc.eu/nos-aides"},
    {"name": "Europe Centre-Val de Loire", "cat": "Europe en Régions", "region": "Centre-Val de Loire", "url": "https://www.europeocentre-valdeloire.eu/identifier-votre-financement/"},
    {"name": "Europe Bretagne", "cat": "Europe en Régions", "region": "Bretagne", "url": "https://europe.bzh/aides/"},
    {"name": "Europe Normandie", "cat": "Europe en Régions", "region": "Normandie", "url": "https://www.europe-en-normandie.eu/tous-les-financements-par-thematique"},
    {"name": "Europe Hauts-de-France", "cat": "Europe en Régions", "region": "Hauts-de-France", "url": "https://europe-en-hautsdefrance.eu/jai-un-projet/je-trouve-un-financement"},
    {"name": "Europe Grand Est", "cat": "Europe en Régions", "region": "Grand Est", "url": "https://beeurope.grandest.fr/aides/"},
    {"name": "Europe IDF", "cat": "Europe en Régions", "region": "IDF", "url": "https://www.europeidf.fr/jai-un-projet"},
    {"name": "Europe Guadeloupe", "cat": "Europe en Régions", "region": "Guadeloupe", "url": "https://www.europe-guadeloupe.fr/jai-un-projet/les-appels-a-projets/"},
    # Régions
    {"name": "Région Nouvelle-Aquitaine", "cat": "Régions", "region": "Nouvelle-Aquitaine", "url": "https://les-aides.nouvelle-aquitaine.fr/"},
    {"name": "Région Occitanie", "cat": "Régions", "region": "Occitanie", "url": "https://www.laregion.fr/-Toutes-les-aides-"},
    {"name": "Région PACA", "cat": "Régions", "region": "PACA", "url": "https://www.maregionsud.fr/aides-et-appels-a-projets"},
    {"name": "Région AURA", "cat": "Régions", "region": "AURA", "url": "https://www.auvergnerhonealpes.fr/aides"},
    {"name": "Région Bourgogne-FC", "cat": "Régions", "region": "Bourgogne-FC", "url": "https://www.bourgognefranchecomte.fr/guide-des-aides"},
    {"name": "Région Pays de la Loire", "cat": "Régions", "region": "Pays de la Loire", "url": "https://www.paysdelaloire.fr/les-aides"},
    {"name": "Région Centre-Val de Loire", "cat": "Régions", "region": "Centre-Val de Loire", "url": "https://www.centre-valdeloire.fr/le-guide-des-aides-de-la-region-centre-val-de-loire"},
    {"name": "Région Bretagne", "cat": "Régions", "region": "Bretagne", "url": "https://www.bretagne.bzh/aides/"},
    {"name": "Région Normandie", "cat": "Régions", "region": "Normandie", "url": "https://aides.normandie.fr/"},
    {"name": "Région Hauts-de-France", "cat": "Régions", "region": "Hauts-de-France", "url": "https://guide-aides.hautsdefrance.fr/"},
    {"name": "Région Grand Est", "cat": "Régions", "region": "Grand Est", "url": "https://www.grandest.fr/aides/"},
    {"name": "Région IDF", "cat": "Régions", "region": "IDF", "url": "https://www.iledefrance.fr/aides-services"},
    # Opérateurs nationaux
    {"name": "ADEME entreprises", "cat": "Opérateur national", "region": "ADEME", "url": "https://agirpourlatransition.ademe.fr/entreprises/aides-financieres"},
    {"name": "ADEME collectivités", "cat": "Opérateur national", "region": "ADEME", "url": "https://agirpourlatransition.ademe.fr/collectivites/financez-vos-projets"},
    {"name": "Bpifrance", "cat": "Opérateur national", "region": "Bpifrance", "url": "https://www.bpifrance.fr/nos-solutions/financement/financement-expertise"},
    {"name": "Aides Territoires", "cat": "Opérateur national", "region": "Aides Territoires", "url": "https://aides-territoires.beta.gouv.fr/portails/gnius/"},
    {"name": "France Agrimer", "cat": "Opérateur national", "region": "France Agrimer", "url": "https://www.franceagrimer.fr/Accompagner/Dispositifs-par-filiere/Aides-nationales/Grandes-cultures"},
    {"name": "CNL", "cat": "Opérateur national", "region": "CNL", "url": "https://centrenationaldulivre.fr/"},
    {"name": "ANS", "cat": "Opérateur national", "region": "ANS", "url": "https://www.agencedusport.fr/aides-et-subventions"},
    {"name": "CNM", "cat": "Opérateur national", "region": "CNM", "url": "https://cnm.fr/aides-financieres/"},
    # DREETS
    {"name": "DREETS Nouvelle-Aquitaine", "cat": "Opérateur national", "region": "DREETS", "url": "https://nouvelle-aquitaine.dreets.gouv.fr/"},
    {"name": "DREETS Occitanie", "cat": "Opérateur national", "region": "DREETS", "url": "https://occitanie.dreets.gouv.fr/"},
    {"name": "DREETS PACA", "cat": "Opérateur national", "region": "DREETS", "url": "https://paca.dreets.gouv.fr/"},
    {"name": "DREETS AURA", "cat": "Opérateur national", "region": "DREETS", "url": "https://auvergne-rhone-alpes.dreets.gouv.fr/"},
    {"name": "DREETS Bretagne", "cat": "Opérateur national", "region": "DREETS", "url": "https://bretagne.dreets.gouv.fr/"},
    {"name": "DREETS Normandie", "cat": "Opérateur national", "region": "DREETS", "url": "https://normandie.dreets.gouv.fr/"},
    {"name": "DREETS Grand Est", "cat": "Opérateur national", "region": "DREETS", "url": "https://grand-est.dreets.gouv.fr/"},
    {"name": "DREETS Hauts-de-France", "cat": "Opérateur national", "region": "DREETS", "url": "https://hauts-de-france.dreets.gouv.fr/"},
    {"name": "DREETS Pays de la Loire", "cat": "Opérateur national", "region": "DREETS", "url": "https://pays-de-la-loire.dreets.gouv.fr/"},
    {"name": "DREETS Bourgogne-FC", "cat": "Opérateur national", "region": "DREETS", "url": "https://bourgogne-franche-comte.dreets.gouv.fr/"},
    {"name": "DRIEETS IDF", "cat": "Opérateur national", "region": "DRIEETS", "url": "https://idf.drieets.gouv.fr/"},
    # Agences de l'eau
    {"name": "Agence eau Grand Sud-Ouest", "cat": "Opérateur national", "region": "Agences de l\'eau", "url": "https://eau-grandsudouest.fr/aides-financieres"},
    {"name": "Agence eau RMC", "cat": "Opérateur national", "region": "Agences de l\'eau", "url": "https://www.eaurmc.fr/jcms/gbr_5503/fr/les-appels-a-projets"},
    {"name": "Agence eau Loire-Bretagne", "cat": "Opérateur national", "region": "Agences de l\'eau", "url": "https://www.eau-loire-bretagne.fr/sites/agence/home/agence-de-leau/le-12e-programme-2025-2030.html"},
    {"name": "Agence eau Artois-Picardie", "cat": "Opérateur national", "region": "Agences de l\'eau", "url": "https://www.eau-artois-picardie.fr/les-appels-projets-de-lagence-de-leau"},
    {"name": "Agence eau Rhin-Meuse", "cat": "Opérateur national", "region": "Agences de l\'eau", "url": "https://www.eau-rhin-meuse.fr/nos-aides"},
    # CARSAT
    {"name": "CARSAT Aquitaine", "cat": "Opérateur national", "region": "CARSAT", "url": "https://www.carsat-aquitaine.fr/home/partenaires/actualites-partenaire.html"},
    {"name": "CARSAT Occitanie", "cat": "Opérateur national", "region": "CARSAT", "url": "https://www.carsat-mp.fr/"},
    {"name": "CARSAT AURA", "cat": "Opérateur national", "region": "CARSAT", "url": "https://www.carsat-auvergne.fr/"},
    {"name": "CARSAT Bourgogne-FC", "cat": "Opérateur national", "region": "CARSAT", "url": "https://www.carsat-bfc.fr/"},
    {"name": "CARSAT Bretagne", "cat": "Opérateur national", "region": "CARSAT", "url": "https://www.carsat-bretagne.fr/"},
    {"name": "CARSAT Normandie", "cat": "Opérateur national", "region": "CARSAT", "url": "https://www.carsat-normandie.fr"},
    {"name": "CARSAT Hauts-de-France", "cat": "Opérateur national", "region": "CARSAT", "url": "https://carsat-hdf.fr"},
    {"name": "CARSAT Grand Est", "cat": "Opérateur national", "region": "CARSAT", "url": "https://www.carsat-nordest.fr/"},
    {"name": "CGSS Guyane", "cat": "Opérateur national", "region": "CGSS", "url": "https://www.cgss-guyane.fr/appel-a-projets/"},
    # CRESS
    {"name": "CRESS Nouvelle-Aquitaine", "cat": "CRESS", "region": "Nouvelle-Aquitaine", "url": "https://www.cress-na.org/appels-a-projets/"},
    # Départements
    {"name": "Hérault (34)", "cat": "Départements", "region": "Occitanie", "url": "https://herault.fr/321-guide-des-aides-et-appels-a-projet.htm"},
    {"name": "Tarn (81)", "cat": "Départements", "region": "Occitanie", "url": "https://www.tarn.fr/guide-des-aides"},
    {"name": "Pyrénées-Orientales (66)", "cat": "Départements", "region": "Occitanie", "url": "https://www.ledepartement66.fr/nos-aides/"},
    {"name": "Val-de-Marne (94)", "cat": "Départements", "region": "IDF", "url": "https://www.valdemarne.fr/le-conseil-departemental/les-appels-a-projets"},
    {"name": "Haute-Savoie (74)", "cat": "Départements", "region": "AURA", "url": "https://hautesavoie.fr/en-pratique/toutes-les-aides-et-subventions/"},
    {"name": "Nord (59)", "cat": "Départements", "region": "Hauts-de-France", "url": "https://inord.lenord.fr/jcms/prd1_676879/les-dispositifs-departementaux"},
    {"name": "Pas-de-Calais (62)", "cat": "Départements", "region": "Hauts-de-France", "url": "https://www.pasdecalais.fr/subventions-departementales"},
    {"name": "Manche (50)", "cat": "Départements", "region": "Normandie", "url": "https://www.manche.fr/guide-des-aides/"},
    {"name": "Morbihan (56)", "cat": "Départements", "region": "Bretagne", "url": "https://www.morbihan.fr/aides-et-services/rechercher-une-aide"},
    {"name": "Ille-et-Vilaine (35)", "cat": "Départements", "region": "Bretagne", "url": "https://www.ille-et-vilaine.fr/les-aides-du-departement"},
    {"name": "Sarthe (72)", "cat": "Départements", "region": "Pays de la Loire", "url": "https://www.sarthe.fr/guide-des-aides"},
    {"name": "Vendée (85)", "cat": "Départements", "region": "Pays de la Loire", "url": "https://www.vendee.fr/guide-des-aides-et-services"},
    {"name": "Maine-et-Loire (49)", "cat": "Départements", "region": "Pays de la Loire", "url": "https://www.maine-et-loire.fr/aides-et-services/professionnels/guide-des-aides"},
    {"name": "Doubs (25)", "cat": "Départements", "region": "Bourgogne-FC", "url": "https://www.doubs.fr/le-departement/appel-a-projets-a-candidatures-ou-appel-a-manifestation-dinteret/"},
    {"name": "Saône-et-Loire (71)", "cat": "Départements", "region": "Bourgogne-FC", "url": "https://www.saoneetloire.fr/guide-des-aides/"},
    {"name": "Landes (40)", "cat": "Départements", "region": "Nouvelle-Aquitaine", "url": "https://www.landes.fr/guide-des-aides"},
    {"name": "Corrèze (19)", "cat": "Départements", "region": "Nouvelle-Aquitaine", "url": "https://www.correze.fr/services-en-ligne/les-aides"},
    {"name": "Dordogne (24)", "cat": "Départements", "region": "Nouvelle-Aquitaine", "url": "https://demarches.dordogne.fr/demarches/profil-entreprises/subventions/"},
    {"name": "Finistère (29)", "cat": "Départements", "region": "Bretagne", "url": "https://www.finistere.fr/aides-et-services/"},
    {"name": "Calvados (14)", "cat": "Départements", "region": "Normandie", "url": "https://www.calvados.fr/accueil/aides--services.html"},
    {"name": "Seine-Maritime (76)", "cat": "Départements", "region": "Normandie", "url": "https://mesdemarches.seinemaritime.fr/category_e_service/subvention/"},
    {"name": "Somme (80)", "cat": "Départements", "region": "Hauts-de-France", "url": "https://www.somme.fr/services/nos-aides/"},
    {"name": "Oise (60)", "cat": "Départements", "region": "Hauts-de-France", "url": "https://oise.fr/information/portail-des-aides-et-subventions-du-conseil-departemental-de-loise"},
    {"name": "Meurthe-et-Moselle (54)", "cat": "Départements", "region": "Grand Est", "url": "https://meurthe-et-moselle.fr/appels-a-projets/"},
    {"name": "Meuse (55)", "cat": "Départements", "region": "Grand Est", "url": "https://www.meuse.fr/information-transversale/guide-des-aides"},
    {"name": "Haute-Marne (52)", "cat": "Départements", "region": "Grand Est", "url": "https://haute-marne.fr/guide-des-aides/"},
    {"name": "Vosges (88)", "cat": "Départements", "region": "Grand Est", "url": "https://www.vosges.fr/mon-departement/appels-a-projets/"},
    {"name": "Ardennes (08)", "cat": "Départements", "region": "Grand Est", "url": "https://www.cd08.fr/aides-et-subventions"},
    {"name": "Aube (10)", "cat": "Départements", "region": "Grand Est", "url": "https://www.aube.fr/18-aides-du-departement.htm"},
    {"name": "Aisne (02)", "cat": "Départements", "region": "Hauts-de-France", "url": "https://aisne.com/aides"},
    {"name": "Indre (36)", "cat": "Départements", "region": "Centre-Val de Loire", "url": "https://www.indre.fr/fr/subventions"},
    {"name": "Loiret (45)", "cat": "Départements", "region": "Centre-Val de Loire", "url": "https://www.loiret.fr/aides"},
    {"name": "Ariège (09)", "cat": "Départements", "region": "Occitanie", "url": "https://ariege.fr/guide-des-aides/"},
]





CAT_COLORS = {
    'Europe en Régions':'#8b5cf6','DREETS':'#f97316','Régions':'#3b82f6',
    'Départements':'#10b981','Opérateur national':'#f59e0b','CARSAT':'#14b8a6',
    "Agence de l'eau":'#06b6d4','CRESS':'#ec4899',
}

TAGGER_PROMPT = """Tu es une IA de classification sémantique agissant comme un sélecteur dans une banque de tags fermée.
Objectif :
Analyser le contenu de l’article et sélectionner des tags existants UNIQUEMENT à partir de la banque ci-dessous.
RÈGLE DU TAG DE RÉFÉRENCE (OBLIGATOIRE ET STRUCTURANT)
--------------------------------------------------
Avant toute autre analyse, tu dois déterminer la nature du contenu analysé et choisir UN SEUL tag de référence parmi les deux suivants :
- "⭐ Dispositif"
- "⭐ Actualité"
RÈGLE DE CONSTRUCTION DE LA SORTIE :
- La liste de tags retournée DOIT TOUJOURS COMMENCER par le tag de référence.
- Tu dois construire la liste en ajoutant le tag de référence EN PREMIER, puis seulement ensuite les autres tags éventuels.
- Aucun autre tag ne peut être placé avant le tag de référence.
RÈGLE DE DÉCISION :
- Appliquer "⭐ Dispositif" UNIQUEMENT si le contenu décrit un mécanisme opérationnel mobilisable par des bénéficiaires (aide, appel à projets, financement, subvention, prêt, dispositif ouvert).
- NE PAS appliquer "⭐ Dispositif" aux arrêtés, projets d’arrêté, consultations publiques, cadres juridiques, obligations réglementaires ou dérogations administratives individuelles.
- Dans tous ces cas, appliquer "⭐ Actualité".
- En cas de doute, appliquer par défaut "⭐ Actualité".
RÈGLE CONDITIONNELLE SELON LE TAG DE RÉFÉRENCE
--------------------------------------------------
Après avoir choisi le tag de référence :
1) Si le tag de référence est "⭐ Dispositif" :
- Tu dois appliquer la méthodologie structurée (QUI / QUOI / QUE / OÙ / COMMENT / QUAND).
- Tu ne sélectionnes un tag que s’il correspond clairement à une information opérationnelle du dispositif.
2) Si le tag de référence est "⭐ Actualité" :
- Tu NE DOIS PAS utiliser la grille QUI / QUOI / QUE / OÙ / COMMENT / QUAND.
- Tu dois sélectionner librement dans toute la banque les tags qui qualifient le sujet de l’actualité (thème, secteur, territoire, acteurs, guichet, programme, budget, etc.), à condition que l’information soit explicitement présente dans le texte.
- Tu ne dois pas “remplir” des axes : tu sélectionnes uniquement ce qui est utile et évident.
IMPORTANT : Même pour "⭐ Actualité", tu dois utiliser EXCLUSIVEMENT les tags existants dans la banque. Il est interdit de créer, reformuler ou déduire un tag.
RÈGLES D’UTILISATION DES AUTRES TAGS
--------------------------------------------------
- Pour chaque information identifiée dans l’article, tu dois d’abord vérifier si un tag IDENTIQUE existe dans la banque de tags fournie
- Un tag ne peut être sélectionné QUE s’il appartient explicitement à l’une des listes (QUI / QUOI / QUE / OÙ / COMMENT / QUAND)
- Il est STRICTEMENT INTERDIT de produire un mot ou concept qui n’apparaît pas tel quel dans la banque, même s’il semble pertinent ou logique
- Aucun raisonnement sémantique, aucune généralisation, aucune reformulation n’est autorisée
- Les concepts génériques (ex : donnée, territoire, décentralisation, numérique au sens large) ne doivent JAMAIS être transformés en tags s’ils ne figurent pas explicitement dans la banque
- Il n’est PAS obligatoire de sélectionner un tag pour chaque question
- Le nombre de tags peut être nul ou multiple
- Si aucune correspondance STRICTE avec la banque n’existe, ne rien sélectionner
- En cas de doute, ne rien sélectionner
--------------------------------------------------
BANQUE DE TAGS AUTORISÉS (PAR QUESTIONNEMENT)
--------------------------------------------------
QUI — Acteurs / publics visés (bénéficiaires)
Association, Collectivité, Entreprise, Entreprises, PME, TPE, ETI, GE, Start-up, Salariés, SENIORS, Jeunesse, ESS/Insertion, Lauréats, CSE, Comité social et économique (CSE), DRH, Etat, Union européenne
QUOI — Filière / secteur d’activité
Agriculture, Alimentation durable, Artisanat/Commerce, Industrie, Industrie agroalimentaire, Mer / Littoral / Pêche / Aquaculture, Logement / Bâtiment / Construction durable, Mobilité, Tourisme, Thermalisme, Culture, Culture / Audiovisuel, Sport, Sport / Culture, Numérique, Numérique responsable / IA / Data, Énergie / Décarbonation / Sobriété, Biogaz biomasse, Sylviculture, Gestion du littoral, habitat inclusif, Médico-social
QUE — Thématique / enjeu
Transition écologique, Transition énergétique, Adaptation au changement climatique, Biodiversité, Environnement, Environnement / Eau / Biodiversité, développement durable, Économie circulaire / Déchet, Innovation, Innovation / Nouveaux dispositifs, Recherche, Inclusion sociale, cohésion sociale, Santé, Emploi / Formation, Formation, Education, Entrepreneuriat, Développement économique, Développement territorial, Aménagement du territoire, Politique culturelle, Sobriété foncière, Renaturation, Résilience agricole, Catastrophes naturelles, Cybersécurité, Sécurité / Défense / Souveraineté, Réforme / Réglementation, Dialogue social, Sensibilisation, Tendance de fond
OÙ — Territoire
National, Europe, Union européenne, Régions, Auvergne-Rhône-Alpes, Bourgogne-Franche-Comté, Bretagne, Centre-Val de Loire, Corse, Grand Est, Hauts-de-France, Île-de-France, Normandie, Nouvelle-Aquitaine, Occitanie, Pays de la Loire, Sud - PACA, Guadeloupe, Guyane, La Réunion, Martinique, Mayotte, Vendée, Hérault, Italie, Périgord, QPV
COMMENT — Guichet / financeur / mécanisme
AAP, AMI, AO, ADEME, Agence de l'eau, Banque des territoires, Bpifrance, Caisse des dépôts, ANR, Aract, Dares, DDETS, DREETS, CNSA, CRESS, DILCRAH, FDVA, FEADER, FEDER, FSE, FSE+, France 2030, fonds chaleur, Financement régional, Subvention, Prêt, Avance remboursable, Crédit d’impôt, Crédit-bail, Bonification d’intérêt, Fonds propres, Investissement, Investissement public, prise de participation, Invest, PTCE, LEADER, ALCOTRA, ODDS, CARSAT, FEAMPA, Fonds Barnier
QUAND — Temporalité
En continu, En expérimentation, PLF 2026, Clôture 2026, Clôture 2027, Clôture 2028, Clôture 2029, Clôture août 2025, Clôture août 2026, Clôture avril 2025, Clôture avril 2026, Clôture décembre 2025, Clôture décembre 2026, Clôture décembre 2027, Clôture février 2026, Clôture février 2027, Clôture janvier 2026, Clôture janvier 2027, Clôture juillet 2025, Clôture juillet 2026, Clôture juin 2025, Clôture juin 2026, Clôture juin 2027, Clôture mai 2025, Clôture mai 2026, Clôture mars 2025, Clôture mars 2026, Clôture mars 2027, Clôture novembre 2025, Clôture novembre 2026, Clôture octobre 2025, Clôture octobre 2026, Clôture septembre 2025, Clôture septembre 2026
--------------------------------------------------
RÈGLES D’UTILISATION
--------------------------------------------------
- Sélectionner uniquement des tags présents dans la banque ci-dessus
- Il n’est pas obligatoire de sélectionner un tag pour chaque question
- Le nombre de tags peut être nul ou multiple
- Si aucune correspondance exacte n’existe dans la banque, ne rien sélectionner
- En cas de doute, ne rien sélectionner
-------------------------------------------------
RÈGLE SPÉCIFIQUE — GESTION DES ACRONYMES
--------------------------------------------------
Certains tags de la banque « Substanciel » sont des acronymes disposant d’une forme développée connue.
Pour ces acronymes, tu dois appliquer la règle suivante :
- Si l’acronyme apparaît explicitement dans le contenu (ex : "GE", "PME", "AAP"), tu dois sélectionner le tag correspondant.
- Si la forme développée exacte apparaît explicitement dans le contenu (ex : "Grande entreprise", "petite ou moyenne entreprise", "appel à projets"), tu dois sélectionner le tag acronyme correspondant.
- Si la forme développée ET l’acronyme apparaissent ensemble, tu dois également sélectionner le tag acronyme.
Il est STRICTEMENT INTERDIT :
- de créer un nouvel acronyme,
- de sélectionner un acronyme si ni l’acronyme ni sa forme développée exacte ne sont présents dans le texte,
- de déduire un acronyme à partir d’une interprétation approximative.
Dans tous les cas, seul le TAG ACRONYME existant dans la banque doit être sélectionné.
--------------------------------------------------
FORMAT DE SORTIE ATTENDU (STRICT)
--------------------------------------------------
{
  "Substanciel": []
}"""

# ── DB ────────────────────────────────────────────────────────────────────────
def get_db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL non configurée — vérifiez les variables d'environnement Render")
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def init_db():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS articles (
        id SERIAL PRIMARY KEY, hash TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL, url TEXT NOT NULL, summary TEXT,
        tags TEXT DEFAULT '[]', source TEXT, cat TEXT, region TEXT,
        color TEXT, source_url TEXT, scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        pdf_url TEXT DEFAULT NULL
    )""")
    # Migration: add pdf_url if missing on existing DB
    try:
        cur.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS pdf_url TEXT DEFAULT NULL")
        conn.commit()
    except Exception:
        conn.rollback()
    cur.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id SERIAL PRIMARY KEY, source_url TEXT UNIQUE NOT NULL,
        content_hash TEXT, last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        error_count INTEGER DEFAULT 0, status TEXT DEFAULT 'pending'
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS sources_custom (
        id SERIAL PRIMARY KEY, name TEXT NOT NULL, cat TEXT NOT NULL,
        region TEXT DEFAULT '', url TEXT UNIQUE NOT NULL,
        active BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS dispositifs (
        id SERIAL PRIMARY KEY,
        guichet_financeur TEXT, guichet_instructeur TEXT, titre TEXT,
        nature TEXT, beneficiaire TEXT, type_depot TEXT, date_fermeture TEXT,
        objectif TEXT, types_depenses TEXT, operations_eligibles TEXT,
        depenses_eligibles TEXT, criteres_eligibilite TEXT, depenses_ineligibles TEXT,
        montants_taux TEXT, thematiques TEXT, territoire TEXT,
        points_vigilance TEXT, contact TEXT, programme_europeen TEXT,
        source_url TEXT, article_id INTEGER,
        collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS custom_folders (
        id SERIAL PRIMARY KEY, cat TEXT NOT NULL, region TEXT DEFAULT '',
        sort_order INT DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(cat, region)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS source_order (
        url TEXT PRIMARY KEY, cat TEXT, region TEXT, sort_order INT DEFAULT 0
    )""")
    for idx in [
        "CREATE INDEX IF NOT EXISTS idx_cat ON articles(cat)",
        "CREATE INDEX IF NOT EXISTS idx_region ON articles(region)",
        "CREATE INDEX IF NOT EXISTS idx_scraped ON articles(scraped_at DESC)",
    ]:
        cur.execute(idx)
    cur.execute("""CREATE TABLE IF NOT EXISTS veille360_sessions (
        id SERIAL PRIMARY KEY,
        client_name TEXT NOT NULL DEFAULT 'Sans nom',
        project_desc TEXT,
        result_html TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    cur.execute("CREATE TABLE IF NOT EXISTS journal_editions (id SERIAL PRIMARY KEY, title TEXT NOT NULL, edition_date DATE DEFAULT CURRENT_DATE, summaries JSONB NOT NULL DEFAULT '[]', created_at TIMESTAMP DEFAULT NOW())")
    cur.execute("""CREATE TABLE IF NOT EXISTS packages (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS batch_jobs (
        job_id TEXT PRIMARY KEY,
        status TEXT DEFAULT 'running',
        total INTEGER DEFAULT 0,
        done INTEGER DEFAULT 0,
        pkg_id INTEGER,
        pkg_name TEXT,
        results JSONB DEFAULT '[]',
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    try:
        cur.execute("ALTER TABLE dispositifs ADD COLUMN IF NOT EXISTS package_id INTEGER REFERENCES packages(id) ON DELETE SET NULL")
        conn.commit()
    except Exception:
        conn.rollback()
    try:
        cur.execute("ALTER TABLE dispositifs ADD COLUMN IF NOT EXISTS cdc_url TEXT DEFAULT NULL")
        conn.commit()
    except Exception:
        conn.rollback()

    conn.commit(); cur.close(); conn.close()
    log.info("DB ready")

# ── Sources ───────────────────────────────────────────────────────────────────
def get_all_sources():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT name,cat,region,url FROM sources_custom WHERE active=TRUE")
        dynamic = [dict(r) for r in cur.fetchall()]
        cur.close(); conn.close()
        static_urls = {s['url'] for s in SOURCES}
        extra = [s for s in dynamic if s['url'] not in static_urls]
        return SOURCES + extra
    except:
        return SOURCES

# ── Tagger ────────────────────────────────────────────────────────────────────
def tag_article_by_data(title, summary, source, cat, region, url):
    if not ANTHROPIC_API_KEY: return []
    try:
        content = f"Titre : {title}\nRésumé : {summary or ''}\nSource : {source} ({cat})\nRégion : {region}\nURL : {url}"
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001", "max_tokens": 300,
            "system": TAGGER_PROMPT,
            "messages": [{"role":"user","content":content}]
        }).encode()
        req = Request("https://api.anthropic.com/v1/messages", data=payload, headers={
            "Content-Type":"application/json","x-api-key":ANTHROPIC_API_KEY,
            "anthropic-version":"2023-06-01"
        }, method="POST")
        with urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        text = data["content"][0]["text"].strip()
        m = re.search(r'\{.*?"Substanciel".*?\}', text, re.DOTALL)
        parsed = json.loads(m.group() if m else text)
        return [t for t in parsed.get("Substanciel",[]) if isinstance(t,str)]
    except Exception as e:
        log.warning(f"Tagging error: {e}"); return []

# ── Summary extractor ─────────────────────────────────────────────────────────
def extract_clean_summary(text):
    """Return 2-3 clean readable sentences from raw scraped context."""
    if not text: return ''
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = re.split(r'(?<=[.!?])\s+', text)
    clean = []
    for s in sentences:
        s = s.strip()
        if len(s) < 40 or len(s) > 500: continue
        # Skip mostly-uppercase (headers)
        if sum(1 for c in s if c.isupper()) / max(len(s),1) > 0.4: continue
        # Need at least 6 words
        if len(s.split()) < 6: continue
        clean.append(s)
        if len(clean) >= 3: break
    return (' '.join(clean) if clean else text[:280])[:320]

# ── Scraper ───────────────────────────────────────────────────────────────────
KEYWORDS = ['aide','subvention','appel','financement','projet','soutien','dispositif',
            'programme','fonds','investissement','bourse','dotation','crédit']

class PageParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.base = '/'.join(base_url.split('/')[:3])
        self.items = []; self._skip = 0
        self._skip_tags = {'script','style','nav','footer','head','noscript'}
        self._in_link = False; self._href = ''; self._link_text = ''; self._context = []

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags: self._skip += 1
        if self._skip: return
        if tag == 'a':
            d = dict(attrs); href = d.get('href','')
            if href and not href.startswith('#') and not href.startswith('mailto'):
                self._in_link = True; self._href = href; self._link_text = ''

    def handle_endtag(self, tag):
        if tag in self._skip_tags: self._skip = max(0, self._skip-1)
        if tag == 'a' and self._in_link:
            self._in_link = False
            title = self._link_text.strip()
            if title and len(title) > 15 and any(k in title.lower() for k in KEYWORDS):
                href = self._href
                if href.startswith('http'): url = href
                elif href.startswith('//'): url = 'https:' + href
                elif href.startswith('/'): url = self.base + href
                else: url = self.base_url.rstrip('/') + '/' + href
                self.items.append({'title':title[:200],'url':url,'context':' '.join(self._context[-8:])})
            self._link_text = ''; self._href = ''

    def handle_data(self, data):
        if self._skip: return
        text = data.strip()
        if not text: return
        if self._in_link: self._link_text += ' ' + text
        elif len(text) > 20:
            self._context.append(text)
            if len(self._context) > 20: self._context.pop(0)

def scrape_source(source):
    headers = {
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0',
        'Accept-Language':'fr-FR,fr;q=0.9','Accept':'text/html,*/*;q=0.8',
    }
    try:
        req = Request(source['url'], headers=headers)
        with urlopen(req, timeout=15) as resp:
            html = resp.read(300000).decode('utf-8', errors='ignore')
        content_hash = hashlib.md5(html.encode()).hexdigest()
        conn = get_db(); cur = conn.cursor()
        cur.execute('SELECT content_hash FROM snapshots WHERE source_url=%s',(source['url'],))
        snap = cur.fetchone()
        if snap and snap['content_hash'] == content_hash:
            cur.execute('UPDATE snapshots SET last_checked=NOW(),status=%s WHERE source_url=%s',('ok',source['url']))
            conn.commit(); cur.close(); conn.close(); return 0
        parser = PageParser(source['url']); parser.feed(html)
        seen = set(); unique = []
        for item in parser.items:
            if item['url'] not in seen and item['url'] != source['url']:
                seen.add(item['url']); unique.append(item)
        new_count = 0
        for item in unique[:20]:
            h = hashlib.md5(f"{item['url']}:{item['title']}".encode()).hexdigest()
            summary = extract_clean_summary(item.get('context',''))
            try:
                # Tenter de récupérer le CDC au moment du scrape
                cdc_url = None
                try:
                    cdc_url = _scrape_pdf_url(item['url'])
                except Exception:
                    pass
                cur.execute("""INSERT INTO articles (hash,title,url,summary,tags,source,cat,region,color,source_url,pdf_url)
                    VALUES (%s,%s,%s,%s,'[]',%s,%s,%s,%s,%s,%s) ON CONFLICT (hash) DO NOTHING""",
                    (h,item['title'],item['url'],summary,source['name'],source['cat'],
                     source.get('region',''),CAT_COLORS.get(source['cat'],'#4b5a75'),source['url'],cdc_url))
                if cur.rowcount > 0:
                    new_count += 1
            except Exception as e:
                log.warning(f"Insert: {e}"); conn.rollback()
        cur.execute("""INSERT INTO snapshots (source_url,content_hash,last_checked,status,error_count)
            VALUES (%s,%s,NOW(),'ok',0) ON CONFLICT (source_url) DO UPDATE
            SET content_hash=%s,last_checked=NOW(),status='ok',error_count=0""",
            (source['url'],content_hash,content_hash))
        conn.commit(); cur.close(); conn.close(); return new_count
    except Exception as e:
        log.warning(f"Error {source['name']}: {e}")
        try:
            conn = get_db(); cur = conn.cursor()
            cur.execute("""INSERT INTO snapshots (source_url,content_hash,last_checked,status,error_count)
                VALUES (%s,'',NOW(),'error',1) ON CONFLICT (source_url) DO UPDATE
                SET last_checked=NOW(),status='error',error_count=snapshots.error_count+1""",(source['url'],))
            conn.commit(); cur.close(); conn.close()
        except: pass
        return 0

def run_scraper():
    all_sources = get_all_sources()
    log.info(f"Scraping {len(all_sources)} sources")
    total = 0
    for i, s in enumerate(all_sources):
        n = scrape_source(s); total += n
        if n: log.info(f"[{i+1}/{len(all_sources)}] {s['name']}: {n} new")
        time.sleep(0.5)
    log.info(f"Done — {total} new"); return total

# ── API ───────────────────────────────────────────────────────────────────────
@app.route('/api/articles')
def get_articles():
    cat=request.args.get('cat'); region=request.args.get('region')
    search=request.args.get('q'); tag=request.args.get('tag')
    page=int(request.args.get('page',0)); limit=int(request.args.get('limit',200))
    has_cdc=request.args.get('has_cdc')
    q='SELECT * FROM articles WHERE 1=1'; p=[]
    if cat: q+=' AND cat=%s'; p.append(cat)
    if region: q+=' AND region=%s'; p.append(region)
    if has_cdc=='1': q+=" AND pdf_url IS NOT NULL AND pdf_url != ''"
    if search:
        s=f'%{search}%'
        q+=' AND (title ILIKE %s OR summary ILIKE %s OR source ILIKE %s OR region ILIKE %s)'
        p.extend([s,s,s,s])
    if tag: q+=' AND tags LIKE %s'; p.append(f'%{tag}%')
    has_tags=request.args.get('has_tags')
    if has_tags: q+=" AND tags IS NOT NULL AND tags != '[]' AND tags != ''"
    q+=' ORDER BY scraped_at DESC LIMIT %s OFFSET %s'; p.extend([limit,page*limit])
    conn=get_db(); cur=conn.cursor(); cur.execute(q,p)
    rows=cur.fetchall(); cur.close(); conn.close()
    result=[]
    for r in rows:
        d=dict(r)
        try: d['tags']=json.loads(d.get('tags') or '[]')
        except: d['tags']=[]
        if d.get('scraped_at'): d['scraped_at']=d['scraped_at'].isoformat()
        result.append(d)
    return jsonify(result)

@app.route('/api/tag-article', methods=['POST'])
def tag_article_endpoint():
    data=request.get_json(); aid=data.get('id')
    if not aid: return jsonify({'error':'id required'}),400
    conn=get_db(); cur=conn.cursor()
    cur.execute('SELECT * FROM articles WHERE id=%s',(aid,))
    row=cur.fetchone(); cur.close(); conn.close()
    if not row: return jsonify({'error':'not found'}),404
    row=dict(row)
    tags=tag_article_by_data(row['title'],row['summary'],row['source'],row['cat'],row['region'],row['url'])
    conn=get_db(); cur=conn.cursor()
    cur.execute('UPDATE articles SET tags=%s WHERE id=%s',(json.dumps(tags,ensure_ascii=False),aid))
    conn.commit(); cur.close(); conn.close()
    return jsonify({'id':aid,'tags':tags})

@app.route('/api/stats')
def get_stats():
    conn=get_db(); cur=conn.cursor()
    today=datetime.now().strftime('%Y-%m-%d')
    cur.execute('SELECT COUNT(*) as c FROM articles'); total=cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) as c FROM articles WHERE scraped_at::date=%s",(today,)); today_c=cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) as c FROM snapshots WHERE status='ok'"); ok=cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) as c FROM snapshots WHERE status='error'"); err=cur.fetchone()['c']
    cur.execute("SELECT MAX(last_checked) as t FROM snapshots"); last=cur.fetchone()['t']
    cur.execute("SELECT COUNT(*) as c FROM articles WHERE tags!='[]' AND tags IS NOT NULL"); tagged=cur.fetchone()['c']
    cur.close(); conn.close()
    return jsonify({'total':total,'today':today_c,'sources_ok':ok,'sources_error':err,
        'sources_total':len(get_all_sources()),'last_scrape':last.isoformat() if last else None,'tagged':tagged})

@app.route('/api/nav')
def get_nav():
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT cat,region,COUNT(*) as count FROM articles GROUP BY cat,region ORDER BY cat,region")
    rows=cur.fetchall()
    # Also get custom folders (may have 0 articles)
    try:
        cur.execute("SELECT cat,region FROM custom_folders ORDER BY sort_order,cat,region")
        folder_rows=cur.fetchall()
    except:
        folder_rows=[]
    cur.close(); conn.close()
    nav={}
    # Seed empty custom folders first
    for f in folder_rows:
        cat=f['cat']
        if cat not in nav: nav[cat]={'total':0,'regions':{},'color':CAT_COLORS.get(cat,'#4b5a75')}
        if f['region'] and f['region'] not in nav[cat]['regions']:
            nav[cat]['regions'][f['region']]=0
    # Fill with article counts
    for r in rows:
        cat=r['cat']
        if cat not in nav: nav[cat]={'total':0,'regions':{},'color':CAT_COLORS.get(cat,'#4b5a75')}
        nav[cat]['total']+=r['count']
        if r['region']: nav[cat]['regions'][r['region']]=nav[cat]['regions'].get(r['region'],0)+r['count']
    return jsonify(nav)

@app.route('/api/tags')
def get_all_tags():
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT tags FROM articles WHERE tags!='[]' AND tags IS NOT NULL")
    rows=cur.fetchall(); cur.close(); conn.close()
    counts={}
    for row in rows:
        try:
            for t in json.loads(row['tags']): counts[t]=counts.get(t,0)+1
        except: pass
    return jsonify([{'tag':t,'count':c} for t,c in sorted(counts.items(),key=lambda x:x[1],reverse=True)])

@app.route('/api/sources', methods=['GET'])
def api_get_sources():
    all_src=get_all_sources()
    static_urls={s['url'] for s in SOURCES}
    return jsonify([{'name':s['name'],'cat':s['cat'],'region':s.get('region',''),
        'url':s['url'],'type':'static' if s['url'] in static_urls else 'dynamic'} for s in all_src])

@app.route('/api/sources', methods=['POST'])
def api_add_source():
    data=request.get_json()
    if not all(k in data for k in ['name','cat','url']):
        return jsonify({'error':'name, cat, url required'}),400
    try:
        conn=get_db(); cur=conn.cursor()
        cat=data['cat']; region=data.get('region','')
        # Insert source
        cur.execute("""INSERT INTO sources_custom (name,cat,region,url)
            VALUES (%s,%s,%s,%s) ON CONFLICT (url) DO UPDATE SET active=TRUE""",
            (data['name'],cat,region,data['url']))
        # Also register the folder in custom_folders so it appears in nav immediately
        cur.execute("""INSERT INTO custom_folders (cat,region,sort_order)
            VALUES (%s,%s,0) ON CONFLICT DO NOTHING""", (cat,''))
        if region:
            cur.execute("""INSERT INTO custom_folders (cat,region,sort_order)
                VALUES (%s,%s,0) ON CONFLICT DO NOTHING""", (cat,region))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'status':'added'})
    except Exception as e:
        return jsonify({'error':str(e)}),500

@app.route('/api/sources/<path:url>', methods=['DELETE'])
def api_delete_source(url):
    static_urls={s['url'] for s in SOURCES}
    if url in static_urls: return jsonify({'error':'Cannot delete static source'}),403
    conn=get_db(); cur=conn.cursor()
    cur.execute("UPDATE sources_custom SET active=FALSE WHERE url=%s",(url,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({'status':'deleted'})

COLLECT_PROMPT = """Tu es un expert en analyse de dispositifs de financement publics français.
Analyse le contenu fourni et extrais une grille structurée avec une précision maximale.
Si un cahier des charges (CDC) est fourni, il fait AUTORITÉ — analyse-le en PRIORITÉ absolue.

━━━ CHAMPS À REMPLIR ━━━

guichet_financeur
L'organisme qui APPORTE les fonds — celui dont le budget est engagé.
RÈGLE CRITIQUE : distingue toujours financeur et instructeur.
  • Fonds européens (FEDER, FSE, FEADER, FEAMPA...) → le fonds européen EST le financeur, même si une région instruit
  • Plusieurs cofinanceurs → les lister séparés par " | " (ex: "FEDER | Région Bretagne")
  • ADEME, Bpifrance, CDC, banques publiques → financeur direct
  • Ministères, ANAH, ANCT → financeur direct
  NE PAS confondre avec l'instructeur : "le paiement est assuré par X" ≠ X est le financeur

guichet_instructeur
L'organisme qui REÇOIT et INSTRUIT les dossiers — le contact opérationnel.
Souvent : Région, DREAL, DDETS, agence régionale, opérateur délégué.
Peut être identique au financeur si non précisé.

titre
Nom exact du dispositif, tel qu'écrit dans la source. Ne pas inventer ni abréger.

nature
UNE valeur parmi : Subvention | Prêt | Avance remboursable | Garantie | Crédit d'impôt | Investissement en fonds propres | Aide en nature | Exonération fiscale

beneficiaire
LISTE ABSOLUMENT TOUS les types de bénéficiaires éligibles, séparés par " | ".
Table de correspondance obligatoire :
  • Entreprise, société, SAS, SARL, SA, holding → Entreprise
  • Selon taille explicitement mentionnée → ajouter aussi PME, TPE, ETI, GE, Start-up
  • Collectivité, commune, EPCI, agglo, métropole, département, région, syndicat mixte, établissement public → Collectivité
  • Association, fondation, ONG, fédération → Association
  • Exploitant agricole, agriculteur, coopérative agricole, groupement agricole → Agriculteur
  • Université, laboratoire, organisme de recherche, EPIC de recherche → Chercheur
  • SCOP, SCIC, coopérative, structure ESS → ESS
  • Personne physique, ménage, propriétaire, locataire, particulier → Particulier
IMPORTANT : si le texte dit "collectivités et leurs opérateurs publics et privés" → inclure Collectivité + Entreprise + Association

type_depot
Applique ces règles STRICTEMENT DANS L'ORDRE — s'arrête à la première qui s'applique :
  1. Le dispositif est FERMÉ / CLOS / EXPIRÉ, ou la date limite est DÉJÀ PASSÉE → "Clôturé"
  2. Une DATE LIMITE DE DÉPÔT explicite et FUTURE est mentionnée → mettre cette date directement (ex: "30/10/2026")
  3. Renouvellement en attente, prochain appel annoncé → "En attente de renouvellement"
  4. Dépôt continu, guichet permanent, aucune échéance → "Au fil de l'eau"
ATTENTION RÈGLE 2 : si une date limite existe, mettre la date elle-même dans type_depot, PAS le mot "Date".
"au fil de l'eau" dans le texte peut désigner le PROCESSUS D'INSTRUCTION et non le dépôt — ne pas confondre.

date_fermeture
Date limite de candidature (JJ/MM/AAAA) si future, ou date de clôture passée si clôturé.
Si type_depot contient déjà la date → répéter la même date ici.
Sinon : "Information non fournie"

objectif
1 phrase synthétique, MAX 180 caractères. Ce que le dispositif finance et pourquoi.

types_depenses
Valeurs parmi [Investissement | Fonctionnement | Étude] séparées par " | "

operations_eligibles
Actions et projets financés. MAX 400 caractères, séparés par " | ". Extraits du contenu réel.

depenses_eligibles
Postes de dépenses couverts. MAX 450 caractères, séparés par " | ". Extraits du contenu réel.

criteres_eligibilite
Conditions d'éligibilité clés. MAX 350 caractères, séparés par " | ". Conditions réelles du texte.

depenses_ineligibles
Ce qui est explicitement exclu. MAX 300 caractères. Uniquement ce qui est écrit noir sur blanc.

montants_taux
Montants min/max, taux, plafonds. MAX 380 caractères. Chiffres réels extraits du texte.

thematiques
Sujets couverts séparés par " | "

territoire
Zone géographique couverte (région, national, européen...)

points_vigilance
⚠️ RÈGLE STRICTE : uniquement des EXIGENCES SPÉCIFIQUES et CONTRAINTES CRITIQUES du dispositif.
Exemples acceptés : délai de dépôt imposé | seuil minimum de dépenses | interdiction de cumul | obligation de contact préalable | règle de minimis | condition de partenariat obligatoire
Exemples REFUSÉS : "consulter le site pour plus d'infos" | "vérifier les conditions" | "document PDF difficile à lire" | tout commentaire sur la qualité de la source
MAX 400 caractères, 3-4 points séparés par " | ". Si aucune contrainte spécifique trouvée → "Information non fournie"

contact
Coordonnées réelles : nom du service, email, téléphone, URL de dépôt. Extraits du texte.

programme_europeen
Nom du programme européen si explicitement mentionné (ex: "FEDER 2021-2027 Bretagne"). Sinon "Information non fournie"

━━━ RÈGLES FINALES ━━━
• Information absente ou incertaine = "Information non fournie" — jamais d'invention
• Séparateur de listes = " | " — jamais de tirets, puces, virgules, ou sauts de ligne
• Réponse UNIQUEMENT en JSON valide, sans texte avant ni après, clés exactes :
guichet_financeur, guichet_instructeur, titre, nature, beneficiaire, type_depot,
date_fermeture, objectif, types_depenses, operations_eligibles, depenses_eligibles,
criteres_eligibilite, depenses_ineligibles, montants_taux, thematiques, territoire,
points_vigilance, contact, programme_europeen"""


TEMPLATE_B64 = "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ERCR0qXKJ8H5XYKKSAk0hjZvCxrIg/idA+7qbaO1ZNY/0t3njou3A2khbpv8LdVX+r6C5TStyW/gVhku0hASnRFvE3iMM8vbCFH3w6VQQ1yKvYy2AHnxrUG+3oSbeUjK9NDLbsa+JQ8GJlflt2nQBw3ghyh4BflOcgVD6W5EeLo/fnfpo2Zr+f3opP0Uf99jya6ag893rspBg2kru3yFZxy/2W2woFASXfurzVneJaZM7zpEAM0kOvfHvCcKnx/WiA2U9HtUZlXSZ/Suwq/RA+np6VMt6GHill9stHqTsfeQC0AFdPDGDyS/Gx5F9EZyVfh9dVy63GPW5WtogBorY3a5zpxV/oLR5rNAvF3wsT6IeXx13h5G/l+tBBoMq+J3QrBL+lrwU0RKRvUF6LDcQuPvpkzfL9HYvYUYOhXcBddRhv1hCusCd8Pa/L0UhdSkyD3nFb/GSYK6+Im7PRcnWCuuQE/yGprWkjJKpqExnGGxemfh2O2xo/0CsCHDpEn/D0SqPDxkBFz7AAAAAElFTkSuQmCCUEsDBAoAAAAAAAAAIQDsNerwflsAAH5bAAAUAAAAcHB0L21lZGlhL2ltYWdlMS5wbmeJUE5HDQoaCgAAAA1JSERSAAAIDgAACasIAwAAAE4c+SgAAAABc1JHQgCuzhzpAAAABGdBTUEAALGPC/xhBQAAAmdQTFRFAAAA////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////nuIqFQAAAM10Uk5TAAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8gISIjJCUmJygpKissLS4vMDEyMzQ1Njc4OTo7PD0+P0BBQkNERUZHSElKS0xNTk9QUVJTVFVWV1hZWltcXV5fYGFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6e3x9fn+AgYKDhIWGh4iJiouMjY6PkJGSk5SVlpeYmZqbnJ2en6ChoqOkpaanqKmqq6ytrq+wsbKztLW2t7i5uru8vb6/wMHCw8TFxsfIycrLzFw2ABgAAAAJcEhZcwAAMsAAADLAAShkWtsAAFfHSURBVHhe7d37v6Xl/MdxqRChoygphb45RqQiKodySgdSzhKlKCIRSSpJdBDKqSRFSiIqkRySYv6o756Z98zstWcf1tp7He77+jyfP80jY2bW+uX9elyPfd33Ex5eBwCUdoMcAIDqTpMDAFDcv18mBwCguGufIAcAoLgPyAEAKO6hF8kBACjuW0+QAwBQ3ElyAACKu28fOQAAxV0yVwNyAABKe6ccAIDi7t5DDgBAcReurwE5AACVvUUOAEBxv9pJDgBAcedtqAE5AACFHSEHAKC4n+8gBwCguLM31oAcAIC6DpEDAFDcjdvIAQAo7vTUgBwAgKoefUVqQA4AQFXXJQbkAACU9cHEwBOekP8AABTz+K6JAacDAFDVFWmBOXIAAGo6Pi0wRw4AQEl3PyctMEcOAEBJFyQF1pMDAFDSkUmB9eQAAFR0c15muIEcAICKzkwJbCAHAKCgR1+ZEthADgBAQdckBDaSAwBQ0CkJgY3kAADUc/9+CYGN5AAA1PP1dEDIAQCo523pgJADAFDOr3ZJB4QcAIByPpcM2EQO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"

LOGO_B64 = {
    'ademe': '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',
    'bpifrance': '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',
    'anah': 'iVBORw0KGgoAAAANSUhEUgAAAPAAAABICAYAAADIzHiKAAAFKUlEQVR4nO3da0xbZRzH8d8plI6uactFaMd1AZaBbhPYgGyQJU6nDoJkcTNmaOaCidkLzGI0xuhm9kJfmBjmOyfRaDTReGEqbsHAC0eMROe4iBsZKsk2VoHIxl1oKb7oPG3phSHQ03/8fZIle8459DnJ8u1zzmHJURBOXfNC2P1EtPYaq5RQu4LvYLhE0SdIyLqAgxgvUXQK0qZuqQOIKIosalQXagcRRSmfVnWLNxCRALebDbwHJiIxFK6+RHJxBSYSjAETCcaAiQRjwESCMWAiwRgwkWAMmEgwBkwkGAMmEowBEwnGgIkEY8BEgjFgIsEYMJFgDJhIMAZMJBgDJhKMARMJxoCJBGPARIIxYCLBGDCRYLFan8D/XdPRYtQU2vy2FRz/DpcdkxqdkVdNoQ1NR4vV8ZZXz6N3cELDM6LFuAJrKMGox74tKQHba8vSNDgbkogBa+jgDjviYgP/CQ6VpkEJ+UZYIi8GrCHflXbW5Vb/npUUj/LcRC1OiYThPbBGspPisSvHG2lD6wDq92QjXh8DwBN3e/+o388Euye1mQ04UZ2HokwLnPMLaO8fxYuf9+HXG/73qvdmmNF5vMJvm3thAeMzLlwZmkJzzzBOtQ1gfMYV9rzvz0++o/koMrgCa6S2zP8y+aOOQbT0jqjjA9uDX177OrwzHd8eK0V5biKMcTGwxMeiamsK2p4rhTl+6e9mnaLAatSjZKMVJx/ZhAsvlyNxvX7N5qPVx4A1csjn8vn3kWn8MjiBM11D6rYEox6VQR5w+XpmdxYOvn0R1voWHPvkkro91WzAkV0Zfsd2XRuH8vQ3fn+s9S3Yd+pHjEzMAQDyUtbj+QdzVmU+igwGrIHt2RZstpnU8RcX/wQAfN09BJfb+7LIpZ5Gv9U2gM9+dmBsxoWG1gHcnHaq+/LtpjA/6TE248K53hE093i/OPbenbxm89Hq43WPBp4oS/cbN3V6Ah6dcuL8lVHctzkJAFC5NQVWox63fELx1db3l994dMqJBKPnEjjJFBdw/MP33IUj5RkozrLAZjGo99u+7JZ1Ic97ufPR2uMKHGExOgWP7bCrY8fYLDr+uKmO/40ZAAyxOhwotiOU4fFZv7FrPvSrnl94KAdnny3Bo8V2bEw2Bo0XAOJiQv/+ajnzUWRwBY6wvQXJSDUb1LHdYoD7dGXI42vL0vBO+9Wg++40n7hYHV6pylXHnVfH8eS7XehzTMLlXsB7T23D4Z3pYT5hefNR5HAFjrDasqVD8VWRl4jMxPgVzWkzG2AyeL+rP/jhOnoHJ+ByL0CnKCjJtq7o80k7XIEjyGSIRU1hqjr++KcbePx0Z8Bx+XYTLp3cDQBQFM8T69fP/vaf5x2ZmMPfTjfW6T3f1/uLbPj0ggPOeTdOVG9CwQY+gJKKK3AE7S+ywRjnvfc80zkU9LjLjkn0D0+p49rSlf3f6BnnPBpaB9RxRV4irr+xB0NvPoDqban4qjv4eVD0Y8AR5PtroTmXG+d6h0Me+6VP3AUbTCjMNK9o7pea+lD3fg+6r41jem4eIxNz+LBjEKWvfQ/HrdmlP4CikoK6Zj6bIBKKKzCRYAyYSDAGTCQYAyYSjAETCcaAiQRjwESCMWAiwRgwkWAMmEgwBkwkGAMmEowBEwnGgIkEY8BEgjFgIsEYMJFgDJhIMAZMJJgOjVV8lTSRRI1VCldgIsE8AXMVJpLldrO6xRuIKMr5tKoLtYOIotCiRgPvgRkxUXQK0mb4WPnWBiLthVlU/wHm92kVRrkJHAAAAABJRU5ErkJggg==',
    'anct': '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',
    'cerema': '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',
    'banque_territoires': 'iVBORw0KGgoAAAANSUhEUgAAAPAAAABICAYAAADIzHiKAAAJLElEQVR4nO3deVDU5x3H8fcuh0jFxQMFFBEEUaMCKqEeRYP1jEYNHq1Tq45KPGY8ak01UTvRNGmrjklnvIpJtFbjbcajSRM8YGqLKBaRIIKgUQ4RwUUBXQS2f4grx+6y7nYjv+H7+mvZ57fPfn8Mn32eXfh9UWHOlK16s+NCCPs7tFBlasj4gARXiKbHSJDVDQ6S8ArRNBnJprqxA4QQTUi9jKpNDQghmqhaWVXXv0MIoQA1mW34HlgIoRgqWX2FUC5ZgYVQMAmwEAomARZCwSTAQiiYBFgIBZMAC6FgEmAhFEwCLISCSYCFUDAJsBAKJgEWQsEkwEIomARYCAWTAAub7Jw/DP3BBaR/8stXXUqz5PiqC1CSb94fx6hgH8PXVdV6HpTpSMouZO2BRBJv3HuF1YnmSFZgKxQ9eoJq6jbcfr2T+LQ8RgX78O3q8bRu6fyqSxPNjKzANnhcUcnXybd5O9wfjaszvTq3ISGzAIDYNeMZ3qczANV6PcWlOs6n57NyXwLpuVoAUjdN4zWfthxLvMldbTljQ7vQtpUL56/nM29HHDlFpQBoXJ3ZOjeCCWFdKS7VEZuSQ2tXZ6LC/bmep6XH0i8BuBszi46alnxyKoVlu88DsH/pCKYNCiApu5ABKw8DoFapWDy2D3MjexLgqaG4VMfFrHus3p/I1dtFJs+3fh3fpeSgcW34omXp/KNDurB28gB6dW5DVbWeyzcLiYlN41BCFnppM2ERWYFt4OLkwOiQLsCzVTk9T2sY+/n6E6imbkM1dRttZ3/OF2fTmRDmx/F3x9LCyaHOPBPD/DiTmsvA1UcpKn3C6JAubJwx0DAe884wpg8JJC3nAa+vOsLJyz8QFe5vsi495n/6t0dHsHnmYPK15fgs2MPMLad5s58viR9H0d/fw+Tj6tdxykQdlszfQdOSYytGE+rXnp++f4Sui/aw/nAS0wYFEOjpbrZ+8YIE2Art3FzQH1zA473RRIX7o9fDqn0X0JbpjB5fUl7BX2PTAAj00hDs267OeEJmAYcTssh/UE58Wh4AoX7tAfDv2JopA7sBsPlkCne15Ry9kM2lrEKT9VVXm649wFPD3MheAKw7fInCh4/5LiWHC5kFuDg5sOKtEKOPs7QOS+cP8nbHxckBZ0c1Pbzb4KBWE38tj6hN/yQjX2v6BEQdsoW2QtGjJ7Sf8wXOjmoWj+nLhhkD2R4dQVZBCWdScwF4s58v703qR58u7Wjl4oSqVk99Xw+3Oh94ZRc8NNx+8rQKgBaOz1bp3j5tDWNZBSWG25l3tQzoZnq1NCWsWwdDLfEfTGwwHuCpMfo4S+uwdP70XC3lukpcWzhybMVoAG4VPuLQf7JYvf8CFZVmXoWEgQTYBhWV1Ww+dYWPp4fj6KDmVz/rzpnUXAK9NBxbMRonBzUr9yaw+dQVfD3cyPh0OgAO6rr/IaOy1pJp7r1f7TGVif+KU5+jQ91NVu0Xkt7LD/D9nWKL5rG0DkvnL3z4mDEfnWLVpFAGdvdE4+pMVw83VrwVwr2Sx2w8kfzSdTVHsoW2kUqlQlXzU/t81ejn54FTTXB2x12norKaIG93q+avHYDaq6OxlbKi8tnq7drixeuyf4fWdY65mPVi5R/U3fP/XsfLzB9/LY8xH52izezP6L5kH1k1O5HeXdqafZx4QQJsA2dHNUvH9sVBrUKvh6OJ2QCk3immumaZGtffF093V9ZOHmDVc2QVPOTIhWfzLhvXF093V94O9ze6fU6+dR+AyN6daO/mwi8GBxjeSz+XmV/C52fTAVgd1Z9+fh64tXTi9YAO/GX2EOaPeM2mOiydv7uXO4d+M5KInt5oXFvwsLwCXc3bh4SMAqu+V82RbKGt8PxDLIAy3VMSMgv49B8pfHvlDvBstZq7/RxrovqzZU4ES8Zq2Xn6GmHdOlj1fHO3n6OisooJA/xI+tNkYlNyOHIhu8EnwEt3ncfV2ZHwwI5c/vMUTly6xcmkHxjX37fOcdE7zpF6u5jZbwTx7w8nUaarJD33AXv/lcme+Ayb67Bk/sy7Wv4Wl8GqSaH08/OglYsTt++XsnJvAjtiv7fq+9QcSWN3hdo5fxhzInvW+T2waH5kCy2EgkmAhVAw2UILoWCyAguhYBJgIRRMAiyEgkmAFSx10zT0Bxewa1Fkk55T2I/8IYcNtLvmGL0etrZV+xL441f//ZEqgu3zhvLOiF7y++FmQgJsA/dZnxlub5wxiOXjgwHwit7NXW253Z+/9/IDiphT2I8E2M4s6U7xvDPHVxdvoi3TMbxPZ3RPqwhcvM+isd1x15m15QzJG6YarjUO8nY3/Lnn7K1n2RN/neXjQ5g1LIhuHTXonlaReKOAdYeTiL+WZ6i3/pyN1WfJ+UnnDfuRANvZ9ugI5g3vRezVHN744DghXdvx9XvjGBnsw5A1x0jKfnFB/MQwP6J3xLEgJt5wXbAlY8+FrDhocgu9a1EkM4cGcflmIX6L/k5f33ac+N0Yzvy+E6P+cJLTV3MaPRdjNTR2fneKSg3X+4a+e5Dc4jJCu3qwZGwfkm8VycX7NpIPsezoZbtfJN64R8zpNKMBNTfWmO5e7swcGgTAhuPJ5D0o45vk25xOzcVBrWLd1DCL5qlfgyXnJ5037EtWYDt62e4XmfklDY6xZKwxtS/5y8ir1U0jv4RRwT4MsPAqqfo1WHJ+0nnDviTAdvSy3S8qzTSzMjf2Y6lfg6XnJ5037Ee20HZkbfcLW1Qb+VSoduO5QC9Ng9uXsqxrSG/p+UnnDfuRANuRtd0vbHH7/iMAvNv8hA6algBk5GvZHXcdgN+OD8GrjSsjg32I7N2Jqmo9aw9etOq5LDk/6bxhX7KFtjNru19YK+b0NSJ6ejO4hycFMbMA6LnsS+ZsO0tazgNmDQvi1pYZ6J5WEZ+Wx/ojScSl5Zmf1IzGzq+84ql03rAjuZxQCAWTLbQQCiYBFkLBJMBCKJgEWAgFkwALoWASYCEUTAIshIJJgIVQMAmwEAomARZCwSTAQiiYBFgIBZMAC6FgEmAhFEzNoYWqxg8TQjQ5hxaqZAUWQsGeBVhWYSGUpSaz6vp3CCGauFpZVZsaEEI0QfUy2vA9sIRYiKbJSDbNh1Ua3gnx6plZVP8HeodpXushhOUAAAAASUVORK5CYII=',
    'caisse_depots': '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',
    'france_2030': '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',
    'bpifrance_creation': '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',
    'anr': 'iVBORw0KGgoAAAANSUhEUgAAAPAAAABICAYAAADIzHiKAAAFDklEQVR4nO3dW0hUeQDH8d8cNdNNs0gqIZvVstaXSnEhNCzRWieCyHlZopcIan3oKXyq5556ze0GC10QyofoRsFmBhHs6hC1lW22E9ZiV6V2u5rjPsx2nOOM4zgz4vnD9wPCnP8c/5wYvv6P50yOR3FUVBwcifc8gKkXCDR7xnsu5hOEC7hPrJCtsQPEC7hTrDatiXYA4B5jG7XGewKAO0W2ao0dAOB+X5uN+h0YgDk8rL6AuViBAYMRMGAwAgYMRsCAwQgYMBgBAwYjYMBgBAwYjIABgxEwYDACBgxGwIDBCBgwGAEDBiNgwGAEDBiMgAGDETBgMAIGDEbAgMEIGDAYAQMGy5zuA0C0Awd+0Nq13zrG/P42BYODUft6vQVqb//RMbZ79wXduNHnGNu/v0Hr1y+RJA0MfFBDwy9x55CkkRHp48chPX/+Trdu9aut7Y4ePnyd7D8LU4AV2GXy87NVXb04atznK0t4jubm7+UZ9wMpE+fxSDk5WfJ6C7R583c6ccKv6uri1CdG2hCwyzQ0lCorK/plaWxcmnCUy5cXat26kqSPob39niorW7VmzVHt2/erRv7/0/+ZmZb27KlJel6kHwG7TORK+/nzsP144cI8rVy5MOF5du2qkmWltgy/fz+kixf/VHf33/ZYcfFsFRTMTGlepA8Bu0hRUZ5WrBiN9NSp2/r06Yu9nchp9JcvIUlSaelcbdiwJC3H9eLFO8d2qj8YkD4E7CI+X5njNPnSpYe6efOJvV1fH/v0OtK5cz324507q5SRkfpLPH/+LPvx4OAHDQx8SHlOpAcBu0hj4+gK+/TpW/X2vlZHR9Aey8/PVk1N9AWuSD09r+zvWbRotjZtWpb08eTmZsnnK1NFRZE9duxYIOn5kH7cRnKJ8vJCeb0F9vbVq39Jkq5ff6zh4ZC9kvp8ZY6oY2lt/U21tV5Zlkc7dlTqwoUHkzqWpqZyNTWVO8ZevXqvI0e6dObM3UnNhanFCuwSGzc6V8qOjnDAb99+UiDQb4/X1CxWXl523LkePRrQlSu9ksIXv7ZsKY+7fyIyMjwaHuaTaN2GgF3Asjz2myyk8Gp3585ze/trzJI0Y0aG6utLJ5zz0KHfFQqFg9u+vVLZ2YmfbLW331NV1c/y+9t09+4LSdKcOTnau7dWdXXJ355C+hGwC6xevUhz5+bY2/Pm5aqr6yd1d4e/WlrWOPb3+ZZOOGdf3xudP//Anm+yb8AIhUYUDA6qpeWy43ZWS0vNpH4YYGoRsAtM5l1WkrRqVZEWLJg14X6HD3dpaCh8WykzM7mX+tmzf3X27H17u7Dwm5QujCG9CHia5eZmOd73fPlyryorW6O+/P42ex+Px3nFejz9/f844kvWyZO37dNxSdq6dQX3gl2CgKdZXV2JZs4cPSW9di32FeZgcFB9fW/s7URX7aNHux2nwMl48uSNOjsf29vFxbNVW+tNaU6kBwFPs8gQh4ZCUf+LKFJn52jcJSVztGzZvAnnf/nynU6f/iO1g5R0/Pgtx/a2bStTnhOp81RUHOTeAGAoVmDAYAQMGIyAAYMRMGAwAgYMRsCAwQgYMBgBAwYjYMBgBAwYjIABgxEwYDACBgxGwIDBCBgwGAEDBiNgwGAEDBiMgAGDWYFAM38fFDBQINDsYQUGDGZJ4ZKn+0AAJO5rs9bYAQDuFtmqNd4TANxnbKNRvwMTMeBOsdqMGyuf2gBMv3iL6n/V90sbNCIsJwAAAABJRU5ErkJggg==',
    'dreal': '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',
    'dreets': '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',
    'direccte': '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',
    'carsat': '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',
    'urssaf': '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',
    'msa': 'iVBORw0KGgoAAAANSUhEUgAAAPAAAABICAYAAADIzHiKAAAGH0lEQVR4nO3dfUzUdQDH8c89AAecdIcojz4BAgfqIHxGxVpjJUtvLcyHa0Y1shmjJW22+rdcpmapufm8NaM1E9QRarMW4hQacpoJCQgaCvjAk4I83vUH9IPj7kAYxO9rn9df9/v+ft/f+M29/f7u7redAgPZarQOuJ+IRl96lsLZLsc7GC6R/DgIWWl3EOMlkicHbSoHO4CIZKRfo0pnO4hIpvq0quw/QEQC6GnW/j0wEQlDwdWXSFxcgYkExoCJBMaAiQTGgIkExoCJBMaAiQTGgIkExoCJBMaAiQTGgIkExoCJBMaAiQTGgIkExoCJBMaAiQTGgIkExoCJBMaAiQTGgIkExoCJBMaAiQTGgIkEph7rP+D/LsI7EMXJu2zG/nxwCzMOp9kd66JU4e939sPXQ2czrt9lQkNbs83YokADUmMSsSAgHL4eOnRZLWhqb8H9x00oq69BSV0VNp371unflbliE4yh82zGIg+loriuaohXSKOJK7AMRY2fjPigKLvxpPA4u3gdeT/2ZeSu+hQrw+MwaZwPXFVquKtd4euhQ9T4yVgROhfpc4xO5+s1WiybFms3boqMH8pl0H+AAcvUhphl9mPRLw06L0Tnhy+WrIOi55djdxZlY8q+FGh2rET4wQ34OO8IHjx+OOA5VobFwVVlf3O21hAvnZfkgQHLlDF0Hvw99dJ29MRpWBgQMei85SFzoVaqAAD1rY+Q9ssB3Gq6h7auDlyvv4PP8o8i5MB6HCn+zek5+q60bV0d0uspXhOwKMgwnMuhUcKAZaagphRA9/vdlFkJ0nhqTKL0Or/6utP5fp46m2210v6fuLGtBetyvnY4f6rXRMQF9v5HsaPwJB53tkvbJgNvo+WEActMRsk56RY3ZVYC1EoV9BotVkcsBgCUNVTjdKXZ6fxbTfek13qNFpkrPkJcYIS0Kg/GFGl7m3ykOBenK4uk7aSwhQ5vr2lsMGCZae1sx8GrZwEAAVpvGEPn4a0ZL8Bd7QoA+MZ8ClY4/z26nIpLaO3sve1NDI5F3qrNeJiagQtrPseWJevwrG+w0/lr+6yw5Q01+OP+TWSV5Utjeo0WicGzh319NLIYsAztuXwKFmt3pKkxy/Bu9IsAgJaONhzqiduZG421SPt1P7qsFptxjdoF8/3D8OEcIwpN25CRuNFuJZ3tG4oI70Bp+1jpRQDAyfLf0WnpksZ5Gy0fDFiGKhprkVNxCQCwJCgKwc/4AgC+K8m1+77Xkb1XzmDm4TTsNufgRmOtw2NWRSzCJ/OTbMZej1xqs51Z1h1wXesj5FZdk8YTg2Ohc/N84uuh0cOAZWpXUbbd2G5zzhPPL66rwntn9yJk/3r47UnGmuztyLtdbHPMq2ELpdcqhRKvRcRJ29XN9bh4p/fDsn9jBgA3lQuSwnvn0tjhpxEydbrSjLKGaoTq/AEA52+XwHy3Yljnqm1pQEbJOfzw13lcS96JMH0AAMDH3Us6JmFqtM1DIv6eelg2HnN6TpMhHvuu/Dysv4dGDldgmbLCij3mU9L2bvNPTzTvjajnkTIrAUqF/QMXXVYLapsbpO3qR3XS66G+r10cFInJXhOGNIdGHldgGdteeALbC08MaY5O44kvl76JD2KX45vLOThTaUZl011oXdxhioy3eRDjeHkBAEDrorF57vn7kjyszt5md26DdxCuJe8EACigwFrDEmzO/3E4l0YjhAE/pcK9A/HVc2873V9QU4otBZkAgFemL4CHi5u0r+/XRn0V11WhtL4a0/Xdt/UmQzwDHmMM+CmTWXoRFqsFc/ymY6bPFPi4j4PeTQtXlRr1bc24ev8mjl6/gH1XzqCj56uhvo9Otnd1Sp+AO3K8PB/ps40AgMjxkxAzMRhFd2+M6jWRcwpsNTp/KoCIZI0fYhEJjAETCYwBEwmMARMJjAETCYwBEwmMARMJjAETCYwBEwmMARMJjAETCYwBEwmMARMJjAETCYwBEwmMARMJjAETCYwBEwmMARMJTIn0LP5iM5GI0rMUXIGJBNYdMFdhIrH0NKvsP0BEMtenVaWzHUQkQ/0atX8PzIiJ5MlBmwPHyl9tIBp7Ayyq/wC6dphde/geaQAAAABJRU5ErkJggg==',
    'feader': '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',
    'feder': 'iVBORw0KGgoAAAANSUhEUgAAAPAAAABICAYAAADIzHiKAAAGm0lEQVR4nO3de2yT1x3G8a8dSGjSQAgBghvKLUlZyRBpMxgXDQSFshGttKMt2iSggzGYdu3Yhanaha5/dHSMMm1Fa0GijBW1lUpFNChRKE2jrKWMUhJQSMolkBs0SU0uS2wn9v4gJCZ2gmOb2Sd7PlKk5D2/9/i1pSfnvPZ7Xlvoz5I8T7/tInLnHcm19NXkv0HBFYk+foJs9SlSeEWik59sWm9XICJRpFdGrX01iEiU8sqqtfcGETFAV2Z9z4FFxBgWjb4i5tIILGIwBVjEYAqwiMEUYBGDKcAiBlOARQymAIsYTAEWMZgCLGIwBVjEYAqwiMEUYBGDKcAiBlOARQymAIsYbEikD+D/2eHnZvJwzmi/bd/ZfppXDl0JuM67xu3x0OZwU/e5g+Nldl7Kq+T90sYBP3bvmk63h4YmF0VnGvnFK2V8WtM64Ocs4aUAR4GGJicpj+eHpe5mTXLiUB6dm8qLG6excoGN3+4tZ8u+ipD6HJccx6HnZvLY3FSyJiQydd0xPLodRERpCj1INTa72HX4Cpt3l2GxwO9WZfJQdkpIfdY2Onjz/VoAMtMSmJQaH45DlRAowIPcy4cu4+4aJjfkTgi5P4ul597iDpc75P4kNJpCR4FRw2PxvLPslm2TVh3l0tW2oOq8tTvd1DQ4SEsZxhcnJgb92ADjkuP4xrxUAPYfq6G6vr3/JyZ3nAIcBcJ5DuyPtWvQ9He6GkifvUNeVNrI2m2nB3wcEn6aQg9y8XExjEseBsCZyuag+mhochKz9J/M3/QvWto6mJeVzGubs7H0+ZVb8r+iAA9yG3MndAdtZ15l0P24PR4KSxrZ+sYFAL4+eyyPzE4NxyFKCBTgQWrk3UNZ/7V7eXZ1Jh4P/ObVcvJP1ofc7463L9Hc1gHA5pVTQu5PQqNzYIP4e8Pp+dfP88tdZbfUuA8vo83ZSW2jgwPFV/lrXiVFvS7kGEif3uwtLl46WMnPn5jCzPuSWJSdQsHHof9jkODomxlEDKYptIjBFGARgynAIgbTm1gREOgqJJHbUYAjKNgrq0RuUoCjWN3+hxg7Mo7tb13kJzvPArD/V9k8Od/Gvyuuk/P9IgBK//YVpk1I5EBxHfaWDhZlj8LhcjN17Xv8dMVk1ixOY4otHofLzfEyO1v2VVBY0vOxkvf+DU0uFj+QwqjhsRz84Cob/1yKvcUFgNVi4YfLJ7Luq+NJtyXQ2Ozio3N2ntlzjpKLwV3lJaHRObABAl1zu3xOKsVnPyfz28fIeOoYu56ezvNrp9Lm7GTSqnd54vcnmT99FEf/8GUW+VlauHxOKgWn6vnSD4ooudjMygU2dj89vbt954+y+NOG+6ltdDD+WwWs3nqKZbPGcHzHPB7MGBGupysDoABH0M2LKLx/Jo69y6fOHWCCj5+z8/Khy7Q73WSmJbB6cRoAW9+4QE1DO4dPfEbBx/XEWC1sWZXps/8nF5p47d0artmdvPDmeQAenZtKxj0JpNsSWLf0XgC2/L2Cz647yT9Zz4dldobFWvnZ45ODfRkkBJpCR1C4z4ErqntucZPjNSKWV/Vsr6hp5WFGk5PpO2LeUlf9n+7fsyYmMizW2n1NdeEfZ/vsm25LCOnYJTgKsGGGxPQ9aeroDN9Fdb1XGnn/mbW+MOiVTRJemkJHMWfHjTtexMfFdG+bHOBtbE5UXO/+PeOentExo2ukPFF+3Wcf77p0W8/jnKls5iOv+jn3jwzoGOTOU4Cj2KnzTQAsnJFCyohYVi6wkZ0+PKB9y6ta2ZNfBcCmFZMZlxzHkgdHs3BGCp1uD79+tdxnnxlThvPkfBtjkmLZtOLGSqMDxXWUV7VSUd3K7ndufD79zDfTeSB9BIl3DWHmfUns+N40NiwL/XY9MnCaQkfQ7VYC/XjnWeLjYpg1NYmTf5nHwQ+ukffhNXJnjQmo/7XbTnP2cgtrFqdxae9CHC43hSUNPPuPT3nvdINP/YHiOpbmjGbbd79A0t1Deb2wlg0vlnS3r99eQumlZp5aMp7i7XNobe+k7EoL+45Ws7egKoRXQoKl1UjS/Tnwnvwq1rzwSaQPRwZAU2gRgynAIgbTFFrEYBqBRQymAIsYTAEWMZgCLGIwBVjEYAqwiMEUYBGDKcAiBlOARQymAIsYTAEWMZgCLGIwBVjEYAqwiMGsHMm13L5MRKLOkVyLRmARg90IsEZhEbN0Zdbae4OIRDmvrFr7ahCRKNQro77nwAqxSHTyk83+w6ob3olEXj+D6n8Bt9BErA3j774AAAAASUVORK5CYII=',
    'fse': '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',
    'europe': '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',
    'aura': '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',
    'bretagne': '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',
    'normandie': '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',
    'occitanie': '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',
    'nouvelle_aquitaine': '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',
    'grand_est': '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',
    'hauts_france': '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',
    'ile_france': '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',
    'paca': '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',
    'pays_loire': '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',
    'bourgogne_fc': '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',
    'centre_val': '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',
    'corse': 'iVBORw0KGgoAAAANSUhEUgAAAPAAAABICAYAAADIzHiKAAAJNklEQVR4nO3deVRU5xnH8e/MgBCGObiAglVEWVREG7eoGNGEKCp4jFu0xhNNTE0aramnxhNPrFo16WnSntS18VC32iRNqOKaY6pGxS0iGgWV1QXEHdlHNmH6xwRkgMG5mHG46fP568697533vufw432Hex9GQyP2dMPU2HEhhP1FpaCxdqzBAxJcIZqfhoKsrbtDwitE89RQNrWPayCEaD7qZlRr7YAQonmqnVVt3R1CiOavOrP1PgMLIdRDI7OvEOolM7AQKiYBFkLFJMBCqJgEWAgVkwALoWISYCFUTAIshIpJgIVQMQmwEComARZCxSTAQqiYBFgIFZMAC6FiEmAhVEwCLISKSYAdLGz3BSKTTfzyT5sb3eeI67DneQCdps4mMtmE36tzFJ8rzCTATaBzdcN/5gIGfx1PREIho5PKGX7sDqFfHKd13yGOvjyrei79jMhkE8O+SXF4P67eHeg27yMyv1zHtc/X2PV6fs6cHH0BatOiTVsGbTmEu38w9+MPc2LKIB5kX0HfKRDvERNw8fJ29CU2SdyYkKd6XsjideQnxXPxw3ebdL4wkxlYoV7LonH3D+ahsYgzc8ZRlHGRytISClMTSVu9hFv7YgDQ6HT4z1zA0D2XGJVYRkRCIQM2HaB1v7Am9avRaun82u8I232BUedLeSnuJv3W7sQQ1NOiTaepsxmy/Swjf3hA+JEbdJ//MTpXN4bEnsN38lsA6Dt3JTLZRGSyiQ7jZgD1l8I9/7ieyGQTYbuSLK6j//q9RCabGLBxf4PnNdZP7TF4DR6BIaAHfVdtsxiDUEYCrICLpzftXhgDwK1v/0NFUb7Vtr1WbKDb/D9TWVbCoZc6c3beK7TpP5SBm7/Dc2C44r5Dln5G8MJPKbt3i4MvdOTc+9NpOzSS57+Ox6NHX3ObxesI+cMaXDy9OTVzOHFjQihMS8JzUDhHxz1L1lfrATBeTWVvdw17u2vIjt3cYH/V+w2BIRgCzbOss0drvEKHA3B9+6YGz2usH1vGIJSRACvg7t8dNOZvt3hw/bLVdnq/IDq8PB2AKxs+ofTuTe4d3UfOyYNodDqC5i5T1K/eNwDfiW8CkL52GeW598g5sZ/8xFNoXVzpMvM9c5tXZpnb/H05eWePU1GYx41dW7lzaLfiseadO4nxaioA7UdPAcBnxAQ0Ts48LC7kzoHYn3wMQjn5DKyEptZX05is/zNPj5B+NdvGa2mPtjPT8Xo+wuK4LTx69q/pe9C/4uod1/sGWLQpuHhG0ftbk71jC13nfYTP6MmkrlxUE+Sb3/ybytISRe9lyxiEchJgBYozLpmDq9Hg9jR/4Gr94ogbE0JRxsV6TdpHTX30opFfLkpk7/wnQe+uQO8bQNthUbTuP9S838qyu1E2jEEoJ0toBcpybtcsR30iJuJsaNlgu4ILCTXb+k6B9bZrH7dFQdLpmu1WvUMf28baDG+qqlLUb+mdG+ScPABAr+XRaHQ6jFdTyTt3stHzGurHljEI5STACiUtnkXx5Us46Q30XROLIaAHWhdX3P2DCZy9BJ+IiRivpZG9YwsAXd6Yj4uXD16DR+A58EVMlZWkrVqsqE9jZjrXt20EIOA3i/AI7oOT3kDLXs/R44NVdJryNsbMdLJios1t3vqAVr1DcTa0pMPY12gXPhaAkltZALi0bU+LNm1t6rt6tnXxNN8eu27D7NtQP7aMQSgnS2iFyu7f4djE/vhN+y0+IycR+tX36FxceVhciDEznfunDgGQuGgmxRmX6DBuBi8evEZVeRn3E+LIWLec+6ePKO43acksitIv0HH864R+eYLKEiPFV1K4sftzsnduBeDC0rd/bPMGAzcdpLwgl5t7viBt9RIArsdE06ZfGK36DGb4sTsAHInsTvEV6w9c3D4QS0VRPs6Glpiqqrixa+tjr9VaP7aMQSgjX60ihIrJEloIFZMAC6FiEmAhVEwC/BT1WvGPp1INJP5/yF+hVUzn6obfq3PwjpiIe5du6FxcqSjIw5iVQcpf3yf3zFFHX6KwMwmwSv1cyxqFMhJgO3EyeNBz8TrahY+lvCCXnOP7cTZ41Gun0WrxmzaXjpPeRO8bQEVBLvlJp0lduYiitKQG3tmsblljdWVUYWoihamJln3odHSZ8Xs6jJuBm68/VeVl5CfFk752GbkJ5ueSw3ZfwBDQg9sHd/CwMJ82g8KpKi/jcEQgXkNGEvjOYgz+wZiqKim4dJasmGhz6eSPj202dRziychnYDvptSya9lFTKcq4xPFJz3H3yF68R0yo164pJXZKyhpBWWmjd/jL5P1wgsMjgzgcEUiLNm3ptzoWj+69OT5lIN+F+5G+bjntR022eExUSgUdQwJsB24du+AzchIAV7d8SlnObW7v317vGeimltjZWtYIyksb8xPjyYqJpqqs1NyXX1e0Lq5onFvg3rkbGq2O3IQ4zsydUFNpJaWCjiNLaDuoLoAHy4AZM9MtCg2aXGJnY1kjKC9tNGamW7wuvppCZekDdK5u9F1jrgEuuXGNW/tiSF25iKqKcikVdCAJsL3VDljt4NV5raTEzp5ljabKhxavy3PvEf/rUQTMWkirZwfhZPDgmV/40WXme5Tl3uXKxr9IqaADyRLaDmr/ANcOWN2ZqKkldraWNcJPU9qYmxBH/KxRfDugFYdHBvEgy7yqqF5pSKmg40iA7eBB1mVu/3cbAJ2nz8PF0xvv4eMbXK42tcTOlrJG4IlLG/V+QfT5Wwyt+4Xh7O7Bw+JCqirKAMg///0Tj0M8GalGshNnQ0tClphvI1UU5pNz8gBOz+jxHjEB49VUDo/uBphv8fhNm0vH8a+j9wuyLLHbsYXKEqPVPnSubjVljfrOXS3KGpM/WVBzi8jabaTapY3Vt5Gyd2zh/MIZjzrRaGg3LIpOv3oHj+A+6PTulNzMIjt2M5c3fPzoNtITjEM0nQRYCBWTJbQQKiYBFkLFJMBCqJgEWAgVkwALoWISYCFUTAIshIpJgIVQMQmwEComARZCxSTAQqiYBFgIFZMAC6FiEmAhVEwCLISKaaNS0Dy+mRCiuYlKQSMzsBAqpgVzkh19IUII21VnVlt3hxCieaudVa21A0KI5qduRut9BpYQC9E8NZTNRsMq/7FSCMdrbFL9H/hqJueQZs9rAAAAAElFTkSuQmCC',
    'guadeloupe': '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',
    'martinique': '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',
    'reunion': 'iVBORw0KGgoAAAANSUhEUgAAAPAAAABICAYAAADIzHiKAAAGuUlEQVR4nO3ce3BU5R3G8e9uAoHEXMAkS2II5CINTbgFwiVGnUILWtKiUktbp4IjMp22o1hbKlOpIzqoY512nJbqQK3odNQRh3HAgVagNBMoxQQ1RsAkDaFCNuRG0mQpm8uufwQ2GXIlm+yelz6fv86e87573t2ZZ9/3nJ3zszGQtXu8Ax4XkdG3Pd/W36G+Dyi4ItbTR5DtvRopvCLW1Ec27YM1EBELuSqj9v4OiIhF9ciq/eodImKAy5ntfQ0sIsawafYVMZdmYBGDKcAiBlOARQymAIsYTAEWMZgCLGIwBVjEYAqwiMEUYBGDKcAiBlOARQymAIsYTAEWMZgCbJiffG0K3m3L+eniqdfct/Sp2/BuW85rD8wa+YFJUIQGewD/j/atn8+yzDjf606PlwZXO4Xljfzy3VNU1Lr67Jc0YRxb7s5g66Ez/P5gVYBGK1amAAdRQ2sbsY9+QEJ0GHsfmc892ZPIuimSjE2H8PbxlPbW+7I4VtXEI29+NqzzZT1Z4OeIxWoUYAtwNrvZWexk1uQopjkiSIkNp7LuIgB2m42Hl0xl7a2TSY+PoNHVzrs/nssTuz7n03MtAESPD2XrfTNYMdtBo6uN/SfriRo/hpXZk/i8xkXGpkNA1xI6MzGSHUfOsubPnwAQYrfx2NJU1uQmkRYXjrvDw7HTTWzeU05BWaNvjFf67vqohppmN9+cEc/EiDEcrrjAQ6+XcPbCpcB+aQLoGtgybLbukr/udo9v++UfZvHbVV/F2exm8oYDrH71Y5bPiOfYr/KYOyUagG33z+QHCxIpr3WxYMth9pbWsTJ70pDO+6fVM3l+ZQb/a+8kZePf+e4rx7n9Kzdy8LGFLJke26v9XbMncfBUA4uePUyDq507suL4zb3T/fz0MlwKsAUkRIf5AvfWh9Wca+qazdLjI1iblwzA5t3l1LW08cGJev51uolxY+z8YlkqqXHhfGduAgAv/q0SZ7Obd4qcHP9P86DnneaIYHVuEgAv7KukuukS+0rrOHCynhC7jc0rpvXqc7TyAjuLnTib3RSUNQAwJzna/y9BhkVL6CC68YaxeLct970urGjkwddKfK9zpkZzZWIu2LCoV//0+AiyEiN9bcrOd9/8KjvvInuQYM2b2n28Z9/y8y6WZcYxb0rv/pX1F33bly6vFMJCNQ8EiwIcRA2tbcT/bD95N0/g/YdzyEufyJvr5nDXH4rweqHHqpqsJwv4rLql13t8e5bDt93Xja+R1tHZfZJAnE8Gpp/OIPN4vRSUNfLCXyuBrkCumN21nP7wdPcyODdtQp/9S6tbfEFKiwv37Z/miBj03EVV3e9/c4/2V7aLzgy+DJfgUoAt4qUDVbRc6gBg451pAJTXuni18AsAnshPJzs5mshxocxPieGl72fyo9unUFl3kZ3FTgDWfyMFR1QY985LGHT5DF3L5h1HzgLw86WpJESHsTQzjsUZsXR6vPz6vbLR+KgygrSEtoimi+388dAZNtyRxvyUGJZMj+XAyXrWvfEppdUtPHDLZI5szMXl7uRUTSt/OXqON452he+h10to7/SyYraD45vy2H+ynt2fnOdbsxy0d3oGPO+DO0o44WxlTW4SVc8txt3hoaCsgaf3VPCPyzepxLpU2P069c+Nt7AwNYZdH9Vwz9biYA9HRolm4OvAmtwkJkSM4Z0iJ63uTu5fdBMLU2Nwd3h4fu+/gz08GUWaga8DkeNCefzONFblJJI8cTyNrjYKKy6w5f2KIf0fLOZSgEUMprvQIgZTgEUMpgCLGEwBtjB/qm8Mlap0mE1/I40yVd+Q0aQAB0igq28Mlap0mE0BDjB/q2/UvPh1HFFh/G7/aR59+wQAb62bw6qcRIrPNDPvmUJg6BU0VKXDbLoGDgJ/qm9cMdRH+YZTQUNVOsyhAAeYP9U3evIMMcHXWkFDVTrMoiV0gIxE9Y3huNYKGqrSYRYFOEBGovpGf0JD+g9LICpoqEpH8OhnMoD8rb4B0NbRNcOFjw3x7UuNDe+v+TVTlQ6zKMBBMNzqGwAff/FfABZnxBJ7w1i+l5PInOSoERubqnSYRUvoIPCn+sb6t08QPjaEBakxHN+Ux+6SWvaU1JI/M37ExqcqHebQ44QiBtMSWsRgCrCIwRRgEYMpwCIGU4BFDKYAixhMARYxmAIsYjAFWMRgCrCIwRRgEYMpwCIGU4BFDKYAixjMzvZ82+DNRMRytufbNAOLGKwrwJqFRcxyObP2q3eIiMX1yKq9vwMiYkFXZbT3NbBCLGJNfWRz4LCq4J1I8A0wqX4JLzs6F9K5pfgAAAAASUVORK5CYII=',
    'mayotte': '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',
    'guyane': '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',
}

def generate_dispositif_pptx(data):
    """Generate 2-slide PPTX from embedded template (v3 — logo + fixed title)."""
    import re as _re_pptx, urllib.request as ureq
    from pptx.util import Pt, Emu
    from pptx.oxml.ns import qn
    from lxml import etree

    template_bytes = b64mod.b64decode(TEMPLATE_B64)
    prs = Presentation(io.BytesIO(template_bytes))
    slide1 = prs.slides[0]
    slide2 = prs.slides[1]

    def safe(val):
        v = (val or '').strip()
        return v if v and v != 'Information non fournie' else '—'

    # ── Titre : toujours 24pt, réduction jusqu'à 14pt si trop long ──────────
    def titre_font_size(t):
        return Pt(28)  # Toujours 28pt — taille fixe du nouveau template

    # ── Logo fetch : Google Favicons (sz=128) ────────────────────────────────
    # Correspondance guichet → clé LOGO_B64
    LOGO_KEYS = [
        (['ademe'], 'ademe'),
        (['bpifrance', 'bpi france'], 'bpifrance'),
        (['anah'], 'anah'),
        (['anct', 'cohesion des territoires'], 'anct'),
        (['cerema'], 'cerema'),
        (['banque des territoires'], 'banque_territoires'),
        (['caisse des depots', 'caisse des dépôts', 'cdc'], 'caisse_depots'),
        (['france 2030', 'france2030'], 'france_2030'),
        (['anr', 'agence nationale de la recherche'], 'anr'),
        (['dreal'], 'dreal'),
        (['dreets', 'drieets'], 'dreets'),
        (['direccte'], 'direccte'),
        (['carsat'], 'carsat'),
        (['urssaf'], 'urssaf'),
        (['msa'], 'msa'),
        (['feader'], 'feader'),
        (['feder'], 'feder'),
        (['fse'], 'fse'),
        (['union europeenne', 'union européenne', 'europe', 'commission europeenne'], 'europe'),
        # Régions
        (['auvergne', 'rhone-alpes', 'aura'], 'aura'),
        (['bretagne'], 'bretagne'),
        (['normandie'], 'normandie'),
        (['occitanie'], 'occitanie'),
        (['nouvelle-aquitaine', 'nouvelle aquitaine'], 'nouvelle_aquitaine'),
        (['grand est'], 'grand_est'),
        (['hauts-de-france', 'hauts de france'], 'hauts_france'),
        (['ile-de-france', 'île-de-france', 'ile de france'], 'ile_france'),
        (['paca', 'provence', 'region sud'], 'paca'),
        (['pays de la loire'], 'pays_loire'),
        (['bourgogne', 'franche-comte', 'franche comte'], 'bourgogne_fc'),
        (['centre-val', 'centre val'], 'centre_val'),
        (['corse'], 'corse'),
        (['guadeloupe'], 'guadeloupe'),
        (['martinique'], 'martinique'),
        (['reunion', 'réunion'], 'reunion'),
        (['mayotte'], 'mayotte'),
        (['guyane'], 'guyane'),
    ]

    def fetch_logo_bytes(guichet_name):
        """Essaie Clearbit Logo API, fallback sur PNG embarqué."""""
        import unicodedata, base64 as b64mod2

        nl = unicodedata.normalize('NFD', (guichet_name or '').lower())
        nl = ''.join(c for c in nl if unicodedata.category(c) != 'Mn')

        # Trouver la clé interne
        matched_key = None
        for keywords, key in LOGO_KEYS:
            if any(kw in nl for kw in keywords):
                matched_key = key
                break

        # ── Logo : LOGO_B64 embarqué en priorité, Google favicon en fallback ──
        if matched_key and matched_key in LOGO_B64:
            return b64mod2.b64decode(LOGO_B64[matched_key]), 'png'

        # Fallback : Google favicon service (sz=128, très fiable)
        try:
            domain = None
            DOMAIN_MAP = {
                'ademe': 'ademe.fr', 'bpifrance': 'bpifrance.fr',
                'anah': 'anah.fr', 'anct': 'anct.gouv.fr',
                'cerema': 'cerema.fr', 'banque_territoires': 'banquedesterritoires.fr',
                'caisse_depots': 'caissedesdepots.fr', 'france_2030': 'gouvernement.fr',
                'anr': 'anr.fr', 'dreal': 'ecologie.gouv.fr',
                'dreets': 'travail.gouv.fr', 'carsat': 'carsat.fr',
                'urssaf': 'urssaf.fr', 'msa': 'msa.fr',
                'europe': 'europa.eu', 'feader': 'europe-en-france.gouv.fr',
                'feder': 'europe-en-france.gouv.fr', 'fse': 'europe-en-france.gouv.fr',
                'aura': 'auvergnerhonealpes.fr', 'bretagne': 'bretagne.bzh',
                'normandie': 'normandie.fr', 'occitanie': 'laregion.fr',
                'nouvelle_aquitaine': 'nouvelle-aquitaine.fr', 'grand_est': 'grandest.fr',
                'hauts_france': 'hautsdefrance.fr', 'ile_france': 'iledefrance.fr',
                'paca': 'maregionsud.fr', 'pays_loire': 'paysdelaloire.fr',
                'bourgogne_fc': 'bourgognefranchecomte.fr', 'centre_val': 'centre-valdeloire.fr',
            }
            if matched_key and matched_key in DOMAIN_MAP:
                domain = DOMAIN_MAP[matched_key]
            if domain:
                favicon_url = f'https://www.google.com/s2/favicons?domain={domain}&sz=128'
                req_fav = ureq.Request(favicon_url, headers={'User-Agent': 'Mozilla/5.0'})
                with ureq.urlopen(req_fav, timeout=4) as resp_fav:
                    img_data = resp_fav.read()
                    if len(img_data) > 200:
                        return img_data, 'png'
        except Exception:
            pass

        return None, None

    def add_logo_image(slide, logo_textbox_id, img_bytes, ext):
        """Replace the logo text box with the actual logo image."""
        from pptx.util import Emu
        import tempfile, os

        # Find the text box to get its position
        tb = None
        for shape in slide.shapes:
            if shape.shape_id == logo_textbox_id:
                tb = shape
                break
        if tb is None:
            return

        # Target position: keep x,y of the text box, height=0.45", width auto (max 2.5")
        x = tb.left
        y = tb.top
        h = int(0.45 * 914400)   # 0.45 inches tall
        max_w = int(2.5 * 914400) # max 2.5 inches wide

        # Write img to temp file
        suffix = '.' + ext
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(img_bytes)
            tmp_path = f.name

        try:
            pic = slide.shapes.add_picture(tmp_path, x, y, height=h)
            # Constrain width
            if pic.width > max_w:
                ratio = max_w / pic.width
                pic.width  = max_w
                pic.height = int(pic.height * ratio)
            # Hide the text box (set text to empty)
            if tb.has_text_frame:
                for para in tb.text_frame.paragraphs:
                    for run in para.runs:
                        run.text = ''
        except Exception:
            pass
        finally:
            os.unlink(tmp_path)

    def set_second_para(shape, val):
        """Set text in paragraph[1] — only first run, clear extra runs."""
        paras = list(shape.text_frame.paragraphs)
        if len(paras) > 1:
            runs = list(paras[1].runs)
            if runs:
                runs[0].text = val
                for run in runs[1:]:
                    run.text = ''

    titre = safe(data.get('titre')) or 'Dispositif'
    guichet = safe(data.get('guichet_financeur'))

    # Fetch logo once, reuse on both slides
    logo_bytes, logo_ext = fetch_logo_bytes(guichet)

    # ── SLIDE 1 ──────────────────────────────────────────────────────────────
    for shape in slide1.shapes:
        sid = shape.shape_id
        if not shape.has_text_frame:
            continue

        if sid == 25:
            # Titre dispositif — haut gauche, 24pt, réduit si besoin, word wrap
            tf = shape.text_frame
            tf.word_wrap = True
            shape.width  = int(4.5 * 914400)
            shape.height = int(2.0 * 914400)  # assez haut pour 4 lignes à 14pt
            for para in tf.paragraphs:
                for run in para.runs:
                    run.text = titre
                    run.font.size = titre_font_size(titre)

        elif sid == 26:
            # NATURE / FINANCEUR / INSTRUCTEUR / DEPOT
            paras = list(shape.text_frame.paragraphs)
            # Construire le texte de dépôt
            raw_depot = safe(data.get('type_depot'))
            raw_depot_low = raw_depot.lower()
            fc = safe(data.get('date_fermeture'))
            # Si type_depot contient directement une date, l'utiliser
            if _re_pptx.search(r'\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}', raw_depot):
                depot_txt = f"Clôture : {raw_depot}"
            elif 'clôtur' in raw_depot_low or 'clotur' in raw_depot_low or 'ferm' in raw_depot_low:
                depot_txt = f"Clôturé" + (f" — {fc}" if fc and fc != '—' else "")
            elif 'reouvert' in raw_depot_low or 'réouvert' in raw_depot_low:
                depot_txt = f"Réouverture : {fc}" if fc and fc != '—' else "Réouverture prévue"
            elif 'renouvell' in raw_depot_low or 'attente' in raw_depot_low:
                depot_txt = "En attente de renouvellement"
            elif 'fil' in raw_depot_low or 'continu' in raw_depot_low:
                depot_txt = "Au fil de l'eau"
            elif fc and fc != '—':
                depot_txt = f"Clôture : {fc}"
            else:
                depot_txt = raw_depot if raw_depot != '—' else "Au fil de l'eau"
            vals = [
                safe(data.get('nature')),
                guichet,
                safe(data.get('guichet_instructeur')),
                depot_txt,
            ]
            for i, para in enumerate(paras):
                runs = list(para.runs)
                if len(runs) >= 2 and i < len(vals):
                    runs[1].text = vals[i]

        elif sid == 27:
            set_second_para(shape, safe(data.get('objectif')))

        elif sid == 28:
            set_second_para(shape, safe(data.get('operations_eligibles')))

        elif sid == 29:
            set_second_para(shape, safe(data.get('depenses_eligibles')))

        elif sid == 11:
            # Logo zone — remplacé par image si disponible, sinon texte
            if logo_bytes:
                add_logo_image(slide1, 11, logo_bytes, logo_ext)
            else:
                for para in shape.text_frame.paragraphs:
                    for run in para.runs:
                        run.text = guichet

    # ── SLIDE 2 ──────────────────────────────────────────────────────────────
    for shape in slide2.shapes:
        sid = shape.shape_id
        if not shape.has_text_frame:
            continue

        if sid == 12:
            tf = shape.text_frame
            tf.word_wrap = True
            shape.width  = int(4.5 * 914400)
            shape.height = int(2.0 * 914400)
            for para in tf.paragraphs:
                for run in para.runs:
                    run.text = titre
                    run.font.size = titre_font_size(titre)

        elif sid == 3:
            # NATURE / FINANCEUR / INSTRUCTEUR / DEPOT — identique slide 1
            paras = list(shape.text_frame.paragraphs)
            raw_depot = safe(data.get('type_depot'))
            raw_depot_low = raw_depot.lower()
            fc = safe(data.get('date_fermeture'))
            if _re_pptx.search(r'\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}', raw_depot):
                depot_txt = f"Clôture : {raw_depot}"
            elif 'clôtur' in raw_depot_low or 'clotur' in raw_depot_low or 'ferm' in raw_depot_low:
                depot_txt = f"Clôturé" + (f" — {fc}" if fc and fc != '—' else "")
            elif 'reouvert' in raw_depot_low or 'réouvert' in raw_depot_low:
                depot_txt = f"Réouverture : {fc}" if fc and fc != '—' else "Réouverture prévue"
            elif 'renouvell' in raw_depot_low or 'attente' in raw_depot_low:
                depot_txt = "En attente de renouvellement"
            elif 'fil' in raw_depot_low or 'continu' in raw_depot_low:
                depot_txt = "Au fil de l'eau"
            elif fc and fc != '—':
                depot_txt = f"Clôture : {fc}"
            else:
                depot_txt = raw_depot if raw_depot != '—' else "Au fil de l'eau"
            vals2 = [
                safe(data.get('nature')),
                guichet,
                safe(data.get('guichet_instructeur')),
                depot_txt,
            ]
            for i2, para in enumerate(paras):
                runs = list(para.runs)
                if len(runs) >= 2 and i2 < len(vals2):
                    runs[1].text = vals2[i2]

        elif sid == 14:
            set_second_para(shape, safe(data.get('beneficiaire')))

        elif sid == 15:
            set_second_para(shape, safe(data.get('montants_taux'))[:280])

        elif sid == 16:
            set_second_para(shape, safe(data.get('points_vigilance'))[:280])

        elif sid == 5:
            if logo_bytes:
                add_logo_image(slide2, 5, logo_bytes, logo_ext)
            else:
                for para in shape.text_frame.paragraphs:
                    for run in para.runs:
                        run.text = guichet

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()
@app.route('/api/dispositifs/<int:did>/export-pptx')
def export_pptx(did):
    """Export a dispositif as a 2-slide PPTX."""
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM dispositifs WHERE id=%s", (did,))
    row = cur.fetchone(); cur.close(); conn.close()
    if not row:
        return jsonify({'error': 'not found'}), 404
    data = dict(row)
    try:
        pptx_bytes = generate_dispositif_pptx(data)
        titre = (data.get('titre') or 'dispositif')[:40].replace('/', '-').replace(' ', '_')
        filename = f"dispositif_{titre}.pptx"
        from flask import Response
        return Response(
            pptx_bytes,
            mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        log.error(f"PPTX export error: {e}")
        return jsonify({'error': str(e)}), 500

CONSULTANT_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SubstanCiel — Espace Consultants</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
/* ── RESET & VARS ─────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:        #f4f3ef;
  --surface:   #ffffff;
  --surface2:  #f0efe9;
  --border:    #e2e0d8;
  --text:      #1a1a18;
  --text2:     #5a5a52;
  --muted:     #9a9a90;
  --accent:    #1a3c2e;
  --lime:      #c8e84e;
  --lime-soft: #e8f5b0;
  --tag-bg:    #eef7d8;
  --tag-act:   #1a3c2e;
  --tag-text:  #2a5c3e;
  --radius:    8px;
  --radius-lg: 14px;
  --shadow:    0 2px 12px rgba(0,0,0,0.07);
  --shadow-lg: 0 8px 32px rgba(0,0,0,0.12);
  --sidebar-w: 300px;
  --header-h:  58px;
}

body {
  font-family: 'DM Sans', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  overflow-x: hidden;
}

/* ── HEADER ───────────────────────────────────────────────────────── */
.header {
  position: fixed; top: 0; left: 0; right: 0; z-index: 100;
  height: var(--header-h);
  background: var(--accent);
  display: flex; align-items: center;
  padding: 0 24px; gap: 16px;
  box-shadow: 0 2px 16px rgba(0,0,0,0.15);
}
.header-logo {
  font-family: 'Syne', sans-serif;
  font-weight: 800; font-size: 20px;
  color: var(--lime); letter-spacing: -0.5px;
}
.header-tag {
  font-size: 11px; font-weight: 500;
  color: rgba(200,232,78,0.6);
  letter-spacing: 0.08em; text-transform: uppercase;
}
.header-tabs {
  display: flex; gap: 4px; margin-left: auto;
}
.header-tab-back {
  opacity: 0.6; border-right: 1px solid var(--border);
  margin-right: 4px; padding-right: 16px !important;
  text-decoration: none;
}
.header-tab-back:hover { opacity: 1; color: var(--accent) !important; background: none !important; }
.header-tab {
  padding: 6px 16px; border-radius: 100px;
  font-size: 12px; font-weight: 600;
  cursor: pointer; border: none;
  background: transparent; color: rgba(255,255,255,0.6);
  transition: all 0.15s; font-family: 'DM Sans', sans-serif;
}
.header-tab:hover { color: #fff; background: rgba(255,255,255,0.1); }
.header-tab.active { background: var(--lime); color: var(--accent); }

.header-search {
  display: flex; align-items: center; gap: 8px;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 100px; padding: 5px 14px;
  margin-left: 12px;
}
.header-search input {
  background: none; border: none; outline: none;
  color: #fff; font-size: 12px; font-family: 'DM Sans', sans-serif;
  width: 200px;
}
.header-search input::placeholder { color: rgba(255,255,255,0.4); }
.header-search-icon { font-size: 13px; opacity: 0.5; }

/* ── LAYOUT ───────────────────────────────────────────────────────── */
.layout {
  display: flex;
  padding-top: var(--header-h);
  min-height: 100vh;
}

/* ── SIDEBAR FILTRES ──────────────────────────────────────────────── */
.sidebar {
  width: var(--sidebar-w);
  flex-shrink: 0;
  background: var(--surface);
  border-right: 1px solid var(--border);
  position: fixed;
  top: var(--header-h); bottom: 0;
  overflow-y: auto;
  padding: 16px 0;
}
.sidebar::-webkit-scrollbar { width: 4px; }
.sidebar::-webkit-scrollbar-track { background: transparent; }
.sidebar::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

.sidebar-header {
  padding: 0 16px 12px;
  display: flex; align-items: center; justify-content: space-between;
}
.sidebar-title {
  font-family: 'Syne', sans-serif;
  font-weight: 700; font-size: 12px;
  text-transform: uppercase; letter-spacing: 0.1em;
  color: var(--muted);
}
.sidebar-clear {
  font-size: 11px; color: var(--text2); cursor: pointer;
  padding: 3px 8px; border-radius: 4px;
  background: var(--surface2); border: none;
  font-family: 'DM Sans', sans-serif;
  transition: all 0.15s;
}
.sidebar-clear:hover { background: #ffe0e0; color: #c44; }

.filter-group { margin-bottom: 4px; }
.filter-group.locked > .filter-group-header { opacity: .3; pointer-events: none; cursor: not-allowed; }
.filter-group.locked > .filter-tags { display: none !important; }
.filter-group.locked > .filter-logic-wrap { display: none !important; }
.filter-group.locked > .section-label { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: .1em; color: var(--muted); padding: 14px 0 6px; display: flex; align-items: center; gap: 8px; }
.section-count { background: var(--lime); color: var(--accent); border-radius: 100px; padding: 1px 8px; font-size: 10px; font-weight: 800; }
.card-collect-row { padding: 8px 0 0; }
.btn-collect { padding: 5px 12px; border-radius: 6px; font-size: 11px; font-weight: 700; cursor: pointer; border: 1.5px solid var(--accent); background: var(--surface); color: var(--accent); font-family: 'DM Sans', sans-serif; transition: all .15s; white-space: nowrap; display: inline-flex; align-items: center; gap: 5px; }
.btn-collect:hover:not(:disabled) { background: var(--accent); color: var(--lime); }
.btn-collect:disabled { opacity: .55; cursor: default; }
.collect-icon { font-size: 12px; }
.cdc-inline-link { font-size: 10px; font-weight: 700; color: #1a6bb5; text-decoration: none; background: #e8f3ff; border-radius: 4px; padding: 1px 6px; margin-left: 4px; }
.cdc-inline-link:hover { background: #1a6bb5; color: #fff; }
.cdc-actions { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
.filter-group-header {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 16px; cursor: pointer;
  user-select: none;
  transition: background 0.1s;
}
.filter-group-header:hover { background: var(--surface2); }
.filter-group-label {
  font-size: 10px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.1em;
  color: var(--muted); flex: 1;
}
.filter-group-count {
  font-size: 10px; font-weight: 700;
  background: var(--lime); color: var(--accent);
  border-radius: 100px; padding: 1px 6px;
  display: none;
}
.filter-group-count.show { display: inline; }
.filter-group-arrow { font-size: 10px; color: var(--muted); transition: transform 0.2s; }
.filter-group.open .filter-group-arrow { transform: rotate(90deg); }

.filter-tags {
  display: none; flex-wrap: wrap; gap: 5px;
  padding: 6px 16px 10px;
}
.filter-group.open .filter-tags { display: flex; }

.filter-tag {
  padding: 4px 10px; border-radius: 100px;
  font-size: 11px; font-weight: 500; cursor: pointer;
  background: var(--surface2); color: var(--text2);
  border: 1.5px solid transparent;
  transition: all 0.12s; user-select: none;
}
.filter-tag:hover { border-color: var(--accent); color: var(--accent); }
.filter-tag.active {
  background: var(--accent); color: var(--lime);
  border-color: var(--accent);
}

/* ── MAIN CONTENT ─────────────────────────────────────────────────── */
.main {
  flex: 1;
  margin-left: var(--sidebar-w);
  padding: 20px 24px;
  max-width: 900px;
}

/* ── STATS ROW ────────────────────────────────────────────────────── */
.stats-row {
  display: flex; gap: 10px; margin-bottom: 20px;
}
.stat-chip {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 10px 16px;
  display: flex; flex-direction: column; gap: 2px;
  flex: 1;
}
.stat-chip-val {
  font-family: 'Syne', sans-serif; font-weight: 800; font-size: 22px;
  color: var(--accent);
}
.stat-chip-lbl { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }

/* ── PANELS ───────────────────────────────────────────────────────── */
.panel { display: none; }
.panel.active { display: block; }

/* ── SORT ROW ─────────────────────────────────────────────────────── */
.sort-row { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.sort-label { font-size: 11px; color: var(--muted); }
/* Vue filtre veille */
.vf-row { display:flex; align-items:center; gap:10px; margin-bottom:14px; flex-wrap:wrap; }
.vf-btns { display:flex; gap:6px; }
.vf-btn {
  padding:5px 14px; border-radius:100px; font-size:11px; font-weight:700;
  border:1.5px solid var(--border); background:var(--surface);
  color:var(--muted); cursor:pointer; transition:all .15s; white-space:nowrap;
}
.vf-btn.active { background:var(--accent); color:var(--lime); border-color:var(--accent); }
.vf-btn:hover:not(.active) { border-color:var(--accent3); color:var(--text); }
.vf-right { display:flex; align-items:center; gap:8px; margin-left:auto; flex-wrap:wrap; }
.vf-sort-select {
  padding:5px 10px; border:1px solid var(--border); border-radius:6px;
  font-size:11px; background:var(--surface2); color:var(--muted);
  outline:none; cursor:pointer; font-family:'DM Sans',sans-serif;
}
.vf-sort-select:hover { border-color:var(--accent); color:var(--text); }
.sort-btn {
  padding: 4px 12px; border-radius: 100px;
  font-size: 11px; font-weight: 600; cursor: pointer;
  border: 1.5px solid var(--border);
  background: var(--surface); color: var(--text2);
  transition: all 0.12s; font-family: 'DM Sans', sans-serif;
}
.sort-btn.active { background: var(--accent); color: var(--lime); border-color: var(--accent); }
.result-count { margin-left: auto; font-size: 11px; color: var(--muted); }

/* ── ARTICLE CARDS ────────────────────────────────────────────────── */
.articles-list { display: flex; flex-direction: column; gap: 8px; }
/* ── NOUVELLES CARTES ARTICLE ── */
.acard { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:14px 16px; border-left:3px solid var(--border); transition:box-shadow .15s; }
.acard:hover { box-shadow:0 2px 12px rgba(0,0,0,.07); }
.acard-disp { border-left-color:var(--lime); }
.acard-cdc  { border-left-color:var(--accent3); background:rgba(26,60,46,.02); }
.acard-header { display:flex; align-items:center; gap:8px; margin-bottom:5px; }
.acard-source { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); }
.acard-date   { font-size:10px; color:var(--muted); margin-left:auto; }
.acard-title  { font-family:'Syne',sans-serif; font-weight:700; font-size:14px; line-height:1.35; margin-bottom:5px; }
.card-title-link { color:var(--text); text-decoration:none; }
.card-title-link:hover { color:var(--accent); text-decoration:underline; }
.acard-summary { font-size:12px; color:var(--muted); line-height:1.5; margin-bottom:8px; }
.acard-footer { display:flex; align-items:center; gap:8px; flex-wrap:wrap; padding-top:8px; border-top:1px solid var(--border); }
.acard-tags   { display:flex; gap:4px; flex-wrap:wrap; flex:1; min-width:0; }
.acard-actions{ display:flex; gap:6px; flex-shrink:0; align-items:center; }
.atag { font-size:10px; padding:2px 7px; border-radius:100px; background:var(--surface2); color:var(--muted); border:1px solid var(--border); }
.atag-ref { background:rgba(200,232,78,.15); color:#3a6000; border-color:rgba(200,232,78,.4); font-weight:700; }
.abtn { font-size:11px; font-weight:700; padding:4px 10px; border-radius:6px; cursor:pointer; border:none; white-space:nowrap; }
.abtn-cdc    { background:rgba(200,232,78,.15); color:#3a6000; border:1px solid rgba(200,232,78,.4); }
.abtn-cdc:hover { background:rgba(200,232,78,.3); }
.abtn-nocdc  { background:var(--surface2); color:var(--muted); border:1px solid var(--border); font-weight:400; cursor:default; }
.abtn-collect { background:var(--surface2); color:var(--accent); border:1px solid var(--border); }
.abtn-collect:hover { background:var(--accent); color:white; }
.abtn-collect-cdc { background:rgba(26,60,46,.08); border-color:var(--accent3); color:var(--accent); }
.abtn-resume { background:var(--surface2); color:var(--muted); border:1px solid var(--border); font-size:11px;font-weight:600;padding:4px 10px;border-radius:6px;text-decoration:none; }
.abtn-resume:hover { background:var(--surface); color:var(--accent); }
.abtn-collected { background:rgba(62,207,122,.1); color:#1a7a40; border:1px solid rgba(62,207,122,.3); font-size:11px;font-weight:700;padding:4px 10px;border-radius:6px;cursor:default; }
.abtn-journal { background:var(--surface2); color:var(--muted); border:1px solid var(--border); font-size:13px;padding:3px 8px;border-radius:6px;cursor:pointer; }
.abtn-journal:hover { background:rgba(26,60,46,.08); color:var(--accent); border-color:var(--accent); }
.abtn-journal.added { background:rgba(26,60,46,.1); color:var(--accent); border-color:var(--accent); }

/* ── JOURNAL DA ───────────────────────────────────────────────────── */
/* ── ESPACE PROJET ────────────────────────────────────────────────── */
.ep-list-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:4px; }
.ep-new-btn { padding:7px 18px; border-radius:8px; font-size:12px; font-weight:700; cursor:pointer; border:none; background:var(--accent); color:var(--lime); }
.ep-project-card {
  background:var(--surface); border:1px solid var(--border); border-radius:12px;
  padding:16px 18px; cursor:pointer; transition:all .15s;
  display:flex; align-items:center; gap:14px;
}
.ep-project-card:hover { box-shadow:var(--shadow); border-color:rgba(26,60,46,.3); transform:translateY(-1px); }
.ep-project-card-icon { font-size:24px; width:40px; text-align:center; flex-shrink:0; }
.ep-project-card-main { flex:1; min-width:0; }
.ep-project-card-client { font-family:'Syne',sans-serif; font-weight:700; font-size:14px; color:var(--text); }
.ep-project-card-desc { font-size:12px; color:var(--muted); margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.ep-project-card-meta { font-size:10px; color:var(--muted2); margin-top:4px; }
.ep-project-card-actions { display:flex; gap:6px; flex-shrink:0; }
.ep-del-btn { padding:4px 10px; border:1px solid var(--border); border-radius:6px; font-size:11px; cursor:pointer; background:none; color:var(--muted); }
.ep-del-btn:hover { background:rgba(220,50,50,.08); color:#c03030; border-color:#c03030; }

.ep-header { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; padding-bottom:14px; border-bottom:2px solid var(--border); margin-bottom:14px; flex-wrap:wrap; }
.ep-client-name { font-family:'Syne',sans-serif; font-size:20px; font-weight:800; color:var(--accent); }
.ep-project-desc { font-size:12px; color:var(--muted); margin-top:4px; max-width:500px; line-height:1.55; }
.ep-action-btn { padding:7px 16px; border-radius:8px; font-size:12px; font-weight:700; cursor:pointer; border:1.5px solid var(--border); background:var(--surface2); color:var(--text); transition:all .15s; }
.ep-action-btn:hover { border-color:var(--accent); color:var(--accent); }
.ep-pptx-btn { background:var(--accent); color:var(--lime); border-color:var(--accent); }
.ep-pptx-btn:hover { opacity:.88; }
.ep-back-btn { }

.ep-tabs { display:flex; gap:4px; margin-bottom:16px; border-bottom:2px solid var(--border); }
.ep-tab { padding:8px 18px; border-radius:8px 8px 0 0; font-size:12px; font-weight:700; border:none; background:none; color:var(--muted); cursor:pointer; transition:all .15s; border-bottom:2px solid transparent; margin-bottom:-2px; }
.ep-tab.active { color:var(--accent); border-bottom-color:var(--accent); background:rgba(26,60,46,.04); }
.ep-pane { display:none; }
.ep-pane.active { display:block; }

/* Kanban */
.ep-kanban { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
.ep-kanban-col { background:var(--surface2); border-radius:10px; padding:12px; min-height:200px; }
.ep-kanban-title { font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); margin-bottom:10px; }
.ep-kanban-cards { display:flex; flex-direction:column; gap:8px; }
.ep-disp-card {
  background:var(--surface); border:1px solid var(--border); border-radius:10px;
  padding:12px 14px; display:flex; flex-direction:column; gap:6px;
}
.ep-disp-card-title { font-size:12px; font-weight:700; color:var(--text); line-height:1.3; }
.ep-disp-card-fin { font-size:10px; color:var(--muted); }
.ep-disp-card-actions { display:flex; gap:5px; flex-wrap:wrap; margin-top:4px; }
.ep-disp-btn { padding:3px 9px; border-radius:5px; font-size:10px; font-weight:700; cursor:pointer; border:1px solid var(--border); background:var(--surface2); color:var(--text); transition:all .12s; }
.ep-disp-btn:hover { border-color:var(--accent); color:var(--accent); }
.ep-disp-btn.email { border-color:rgba(91,138,240,.4); color:#4070d0; background:rgba(91,138,240,.06); }
.ep-disp-btn.pptx { border-color:rgba(26,60,46,.3); color:var(--accent); background:rgba(26,60,46,.06); }
.ep-disp-btn.del  { border-color:rgba(200,50,50,.2); color:#c03030; background:rgba(200,50,50,.04); }
.ep-statut-sel { font-size:10px; border:1px solid var(--border); border-radius:5px; background:var(--surface2); color:var(--muted); padding:2px 6px; cursor:pointer; outline:none; }

/* Résultats 360° dans le volet analyse */
.v360-result-table { width:100%; border-collapse:collapse; font-size:12px; margin-top:10px; }
.v360-result-table th { background:var(--accent); color:var(--lime); padding:8px 10px; text-align:left; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; }
.v360-result-table td { padding:8px 10px; border-bottom:1px solid var(--border); vertical-align:top; line-height:1.55; }
.v360-result-table tr:hover td { background:rgba(26,60,46,.03); }
.v360-collect-btn { padding:4px 10px; border-radius:5px; font-size:10px; font-weight:700; cursor:pointer; border:1.5px solid var(--accent); background:none; color:var(--accent); white-space:nowrap; }
.v360-collect-btn:hover { background:var(--accent); color:var(--lime); }
.v360-collect-btn.done { background:rgba(62,207,122,.1); border-color:rgba(62,207,122,.4); color:#1a7a40; cursor:default; }

.journal-masthead {
  border-bottom: 3px solid var(--accent);
  padding-bottom: 14px; margin-bottom: 20px;
  display: flex; align-items: flex-end; justify-content: space-between;
  flex-wrap: wrap; gap: 8px;
}
.journal-name {
  font-family: 'Playfair Display', 'Georgia', serif;
  font-size: 2.4rem; font-weight: 900;
  letter-spacing: -0.03em; color: var(--accent);
  line-height: 1;
}
.journal-name em { font-style: italic; color: var(--lime2,#7ab200); }
.journal-meta { font-size: 11px; color: var(--muted); text-align: right; line-height: 1.6; }
.journal-edition-label {
  font-size: 10px; font-weight: 700; letter-spacing: .12em;
  text-transform: uppercase; color: var(--muted);
  border-top: 1px solid var(--border); border-bottom: 1px solid var(--border);
  padding: 5px 0; margin-bottom: 16px;
  display: flex; justify-content: space-between;
}
.journal-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px; margin-bottom: 20px;
}
.journal-card {
  border: 1px solid var(--border); border-radius: 10px;
  padding: 14px 16px; background: var(--surface);
  display: flex; flex-direction: column; gap: 8px;
  transition: box-shadow .15s;
  position: relative; overflow: hidden;
}
.journal-card::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: var(--border);
}
.journal-card.haute::before { background: var(--accent); }
.journal-card:hover { box-shadow: 0 3px 16px rgba(0,0,0,.08); }
.journal-card-cat {
  font-size: 9px; font-weight: 800; letter-spacing: .12em;
  text-transform: uppercase; color: var(--muted);
}
.journal-card-title {
  font-family: 'Syne', sans-serif; font-weight: 700;
  font-size: 13px; line-height: 1.3; color: var(--text);
}
.journal-card-summary {
  font-size: 12px; color: var(--muted); line-height: 1.6; flex: 1;
}
.journal-card-footer {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 10px; color: var(--muted2);
  border-top: 1px solid var(--border); padding-top: 7px; margin-top: 2px;
}
.journal-card-source { font-weight: 600; }
.journal-card-link { color: var(--accent); text-decoration: none; font-weight: 700; }
.journal-card-link:hover { text-decoration: underline; }
.journal-hist { display: flex; flex-direction: column; gap: 6px; }
.journal-hist-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px;
  cursor: pointer; transition: all .12s;
}
.journal-hist-item:hover { border-color: var(--accent3); box-shadow: 0 2px 8px rgba(0,0,0,.06); }
.journal-hist-title { font-size: 13px; font-weight: 700; flex: 1; }
.journal-hist-meta { font-size: 11px; color: var(--muted); }
.journal-page-controls {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 0; border-top: 1px solid var(--border); margin-top: 8px;
}
.journal-page-btn {
  padding: 5px 14px; border-radius: 6px; font-size: 12px; font-weight: 700;
  border: 1.5px solid var(--border); background: var(--surface2);
  cursor: pointer; transition: all .15s; color: var(--text);
}
.journal-page-btn:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.journal-page-btn:disabled { opacity: .4; cursor: default; }
.journal-page-info { font-size: 12px; color: var(--muted); flex: 1; text-align: center; }

.article-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px 18px;
  transition: all 0.15s;
  cursor: pointer;
  text-decoration: none; color: inherit;
  display: block;
  position: relative;
  overflow: hidden;
}
.article-card::before {
  content: '';
  position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
  background: var(--border); border-radius: 3px 0 0 3px;
  transition: background 0.15s;
}
.article-card:hover { box-shadow: var(--shadow); border-color: #d0cfc7; transform: translateY(-1px); }
.article-card:hover::before { background: var(--lime); }
.article-card.is-dispositif::before { background: var(--lime); }
.article-card.has-cdc { border-color: rgba(168,200,48,0.5); }
.article-card.has-cdc::before { background: var(--lime); }

/* CDC Badge sur la carte */
.cdc-badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 9px; border-radius: 6px;
  font-size: 10px; font-weight: 700;
  background: rgba(168,200,48,0.18);
  color: #4a6800;
  border: 1px solid rgba(168,200,48,0.4);
  text-decoration: none;
}
.cdc-badge:hover { background: rgba(168,200,48,0.32); }
.cdc-badge-missing {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 9px; border-radius: 6px;
  font-size: 10px; font-weight: 600;
  background: var(--surface2);
  color: var(--muted);
  border: 1px solid var(--border);
}

/* Footer carte unifié : tags + CDC + bouton collecter */
.card-footer {
  display: flex; align-items: center; gap: 8px;
  margin-top: 10px; padding-top: 10px;
  border-top: 1px solid var(--border);
  flex-wrap: wrap;
}
.card-footer-tags { display: flex; gap: 4px; flex-wrap: wrap; flex: 1; min-width: 0; }
.card-footer-actions { display: flex; gap: 6px; align-items: center; flex-shrink: 0; }

/* Sort toggle button */
.sort-btn.filter-toggle { background: var(--surface2); border: 1.5px solid var(--border); }
.sort-btn.filter-toggle.on { background: rgba(168,200,48,0.25); color: #3a5800; border-color: #8ab000; font-weight: 800; box-shadow: 0 0 0 2px rgba(168,200,48,0.2); }

.article-card-meta { display:flex; align-items:center; gap:8px; margin-bottom:5px; }
.article-card-source { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.07em; color:var(--muted); white-space:nowrap; }
.article-card-date { font-size:10px; color:var(--muted); white-space:nowrap; margin-left:auto; }
.article-card-title { font-family:'Syne',sans-serif; font-weight:700; font-size:14px; line-height:1.35; color:var(--text); margin-bottom:5px; }
.article-card-summary {
  font-size: 12px; color: var(--text2); line-height: 1.55;
  margin-bottom: 10px; display: -webkit-box;
  -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.article-card-tags { display: flex; flex-wrap: wrap; gap: 5px; }
.article-tag {
  padding: 3px 8px; border-radius: 100px;
  font-size: 10px; font-weight: 600;
  background: var(--tag-bg); color: var(--tag-text);
}
.article-tag.ref { background: var(--accent); color: var(--lime); }
.article-tag.cdc { background: #e8f0ff; color: #2244aa; }

.article-card-actions {
  position: absolute; right: 14px; top: 14px;
  display: flex; gap: 6px; opacity: 0; transition: opacity 0.15s;
}
.article-card:hover .article-card-actions { opacity: 1; }
.card-action-btn {
  width: 28px; height: 28px; border-radius: 6px;
  border: 1px solid var(--border); background: var(--surface);
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; cursor: pointer; transition: all 0.12s;
}
.card-action-btn:hover { background: var(--surface2); border-color: var(--accent); }

/* ── DISPOSITIF CARDS ─────────────────────────────────────────────── */
.disp-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }

/* Contrôles dispositifs */
.disp-controls { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:14px; }
.disp-refresh-btn {
  width:32px; height:32px; border-radius:50%; flex-shrink:0;
  background:var(--accent); color:var(--lime); border:none;
  font-size:16px; font-weight:700; cursor:pointer;
  display:flex; align-items:center; justify-content:center;
  transition:transform .4s ease;
}
.disp-refresh-btn:hover { opacity:.85; }
.disp-refresh-btn.spinning { animation: spin-once .5s ease forwards; }
@keyframes spin-once { to { transform: rotate(360deg); } }
.disp-view-toggle { display:flex; gap:4px; background:var(--surface2); border-radius:8px; padding:3px; border:1px solid var(--border); flex-shrink:0; }
.dv-btn { padding:5px 14px; border-radius:6px; font-size:11px; font-weight:700; border:none; background:none; color:var(--muted); cursor:pointer; transition:all .15s; white-space:nowrap; }
.dv-btn.active { background:var(--surface); color:var(--accent); box-shadow:0 1px 4px rgba(0,0,0,.08); }
.disp-search-input { padding:5px 10px; border:1px solid var(--border); border-radius:6px; font-size:11px; background:var(--surface2); color:var(--text); outline:none; min-width:160px; flex:1; }
.disp-filter-sel { padding:5px 9px; border:1px solid var(--border); border-radius:6px; font-size:11px; background:var(--surface2); color:var(--text); outline:none; cursor:pointer; }

/* Table base de données */
.disp-table { width:100%; border-collapse:collapse; font-size:12px; min-width:1400px; }
.disp-table thead { position:sticky; top:0; z-index:10; }
.disp-table th {
  background:var(--accent); color:var(--lime);
  padding:9px 12px; text-align:left;
  font-size:10px; font-weight:700; letter-spacing:.06em; text-transform:uppercase;
  white-space:nowrap; border-right:1px solid rgba(255,255,255,.1);
  user-select:none;
}
.dt-sort { cursor:pointer; }
.dt-sort:hover { background:rgba(255,255,255,.1); }
.disp-table td {
  padding:9px 12px; border-bottom:1px solid var(--border);
  vertical-align:top; color:var(--text); max-width:200px;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
.disp-table td.wrap { white-space:normal; line-height:1.5; }
.disp-table tr:hover td { background:rgba(26,60,46,.03); }
.disp-table tr:nth-child(even) td { background:rgba(0,0,0,.015); }
.disp-table tr:nth-child(even):hover td { background:rgba(26,60,46,.03); }
.dt-empty { color:var(--muted); font-style:italic; }
.dt-badge { display:inline-block; padding:2px 8px; border-radius:100px; font-size:10px; font-weight:700; }
.dt-badge-depot-eau  { background:rgba(62,207,122,.12); color:#1a7a40; }
.dt-badge-depot-date { background:rgba(245,200,66,.12); color:#8a6000; }
.dt-badge-depot-clos { background:rgba(240,91,91,.1); color:#c03030; }
.dt-badge-depot-att  { background:rgba(167,139,250,.12); color:#5030a0; }
.dt-export-btn { display:inline-flex; align-items:center; gap:4px; padding:4px 10px; border-radius:6px; font-size:10px; font-weight:700; cursor:pointer; border:1.5px solid var(--accent); background:none; color:var(--accent); white-space:nowrap; transition:all .15s; }
.dt-export-btn:hover { background:var(--accent); color:var(--lime); }

/* Sous-menu collect */
.collect-submenu-item {
  width: 100%; display: flex; align-items: center; gap: 12px;
  padding: 12px 16px; background: none; border: none;
  cursor: pointer; text-align: left; font-family: inherit;
  transition: background 0.12s;
}
.collect-submenu-item:hover { background: var(--surface2); }

.disp-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: 16px;
  display: flex; flex-direction: column; gap: 8px;
  transition: all 0.15s;
}
.disp-card:hover { box-shadow: var(--shadow); border-color: #d0cfc7; transform: translateY(-1px); }

.disp-card-header {
  display: flex; align-items: flex-start; gap: 10px;
}
.disp-card-icon {
  width: 36px; height: 36px; border-radius: 8px;
  background: var(--tag-bg); display: flex; align-items: center;
  justify-content: center; font-size: 18px; flex-shrink: 0;
}
.disp-card-title {
  font-family: 'Syne', sans-serif; font-weight: 700; font-size: 13px;
  line-height: 1.3; color: var(--text);
}
.disp-card-financeur { font-size: 11px; color: var(--muted); margin-top: 2px; }

.disp-field { display: flex; flex-direction: column; gap: 2px; }
.disp-field-label { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); }
.disp-field-val { font-size: 11px; color: var(--text2); line-height: 1.4; }
.disp-field-val.empty { color: var(--muted); font-style: italic; }

.disp-card-footer {
  margin-top: auto; padding-top: 10px; border-top: 1px solid var(--border);
  display: flex; gap: 6px;
}
.disp-btn {
  flex: 1; padding: 6px; border-radius: 6px; font-size: 11px; font-weight: 600;
  cursor: pointer; border: 1px solid var(--border); background: var(--surface2);
  color: var(--text2); transition: all 0.12s; font-family: 'DM Sans', sans-serif;
  text-align: center; text-decoration: none; display: flex; align-items: center; justify-content: center; gap: 4px;
}
.disp-btn:hover { background: var(--accent); color: var(--lime); border-color: var(--accent); }
.disp-btn.primary { background: var(--accent); color: var(--lime); border-color: var(--accent); }
.disp-btn.primary:hover { opacity: 0.88; }

/* ── CDC CARDS ────────────────────────────────────────────────────── */
.cdc-list { display: flex; flex-direction: column; gap: 8px; }
.cdc-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: 14px 16px;
  display: flex; align-items: center; gap: 14px;
  transition: all 0.15s;
}
.cdc-card:hover { box-shadow: var(--shadow); border-color: #d0cfc7; }
.cdc-icon {
  width: 40px; height: 40px; border-radius: 10px;
  background: #e8f0ff; display: flex; align-items: center;
  justify-content: center; font-size: 20px; flex-shrink: 0;
}
.cdc-info { flex: 1; min-width: 0; }
.cdc-title {
  font-family: 'Syne', sans-serif; font-weight: 700; font-size: 13px;
  color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.cdc-meta { font-size: 11px; color: var(--muted); margin-top: 2px; }
.cdc-actions { display: flex; gap: 6px; flex-shrink: 0; }
.cdc-btn {
  padding: 6px 12px; border-radius: 6px; font-size: 11px; font-weight: 600;
  cursor: pointer; border: 1px solid var(--border); background: var(--surface2);
  color: var(--text2); transition: all 0.12s; font-family: 'DM Sans', sans-serif;
  text-decoration: none; display: flex; align-items: center; gap: 4px;
}
.cdc-btn:hover { background: #e8f0ff; color: #2244aa; border-color: #b0c8ff; }
.cdc-btn.dl { background: var(--accent); color: var(--lime); border-color: var(--accent); }
.cdc-btn.dl:hover { opacity: 0.88; }

/* ── EMPTY STATE ──────────────────────────────────────────────────── */
.empty-state {
  text-align: center; padding: 60px 20px;
  color: var(--muted); font-size: 14px;
}
.empty-state-icon { font-size: 40px; margin-bottom: 12px; }
.empty-state-title { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 16px; color: var(--text2); margin-bottom: 6px; }

/* ── SPINNER ──────────────────────────────────────────────────────── */
.spinner {
  width: 32px; height: 32px; border-radius: 50%;
  border: 3px solid var(--border); border-top-color: var(--accent);
  animation: spin 0.8s linear infinite; margin: 40px auto;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── MODAL ────────────────────────────────────────────────────────── */
.modal-overlay {
  display: none; position: fixed; inset: 0; z-index: 200;
  background: rgba(0,0,0,0.4); align-items: center; justify-content: center;
}
.modal-overlay.open { display: flex; }
.modal {
  background: var(--surface); border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg); max-width: 680px; width: 90vw;
  max-height: 85vh; overflow-y: auto; padding: 28px;
}
.modal-title {
  font-family: 'Syne', sans-serif; font-weight: 800; font-size: 18px;
  color: var(--accent); margin-bottom: 20px;
}
.modal-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.modal-field { display: flex; flex-direction: column; gap: 4px; }
.modal-field.full { grid-column: 1 / -1; }
.modal-field-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); }
.modal-field-val { font-size: 13px; color: var(--text); line-height: 1.5; }
.modal-field-val.empty { color: var(--muted); font-style: italic; font-size: 12px; }
.modal-footer { margin-top: 24px; display: flex; gap: 8px; justify-content: flex-end; }
.modal-close {
  padding: 8px 20px; border-radius: var(--radius); font-size: 13px; font-weight: 600;
  cursor: pointer; border: 1px solid var(--border); background: var(--surface2);
  color: var(--text); font-family: 'DM Sans', sans-serif; transition: all 0.15s;
}
.modal-close:hover { background: var(--surface); }
.modal-pptx {
  padding: 8px 20px; border-radius: var(--radius); font-size: 13px; font-weight: 600;
  cursor: pointer; border: none; background: var(--accent);
  color: var(--lime); font-family: 'DM Sans', sans-serif; transition: all 0.15s;
}
.modal-pptx:hover { opacity: 0.88; }

/* ── TOAST ────────────────────────────────────────────────────────── */
.toast {
  position: fixed; bottom: 24px; right: 24px; z-index: 999;
  background: var(--accent); color: var(--lime);
  padding: 10px 18px; border-radius: var(--radius);
  font-size: 13px; font-weight: 600;
  box-shadow: var(--shadow-lg);
  transform: translateY(80px); opacity: 0;
  transition: all 0.25s cubic-bezier(.34,1.56,.64,1);
  pointer-events: none;
}
.toast.show { transform: translateY(0); opacity: 1; }

/* ── RESPONSIVE ───────────────────────────────────────────────────── */
@media (max-width: 768px) {
  :root { --sidebar-w: 0px; }
  .sidebar { display: none; }
  .main { margin-left: 0; }
}

/* ── LOAD ANIMATION ───────────────────────────────────────────────── */
.article-card { animation: fadeUp 0.3s ease both; }
@keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
</style>
</head>
<body>

<!-- HEADER -->
<header class="header">
  <div class="header-logo">SubstanCiel</div>
  <div class="header-tag">Espace Collecte</div>
  <nav class="header-tabs">
    <a class="header-tab header-tab-back" href="/app" title="Retour à la curation">← Curation</a>
    <button class="header-tab active" onclick="switchTab('veille', this)">📰 Veille</button>
    <button class="header-tab" onclick="switchTab('dispositifs', this)">🗄 Dispositifs</button>
    <button class="header-tab" onclick="switchTab('cdc', this)">📋 Cahiers des charges</button>
    <button class="header-tab" onclick="switchTab('journal', this)">📰 Journal</button>
    <button class="header-tab" onclick="switchTab('veille360', this)">🔍 Pré-veille 360°</button>
    <button class="header-tab" onclick="switchTab('packages', this)">📦 Packages</button>
  </nav>
  <div class="header-search">
    <span class="header-search-icon">🔍</span>
    <input type="text" id="search" placeholder="Rechercher…" oninput="onSearch()">
  </div>
</header>

<!-- LAYOUT -->
<div class="layout">

  <!-- SIDEBAR FILTRES -->
  <aside class="sidebar" id="sidebar">
    <div class="sidebar-header">
      <span class="sidebar-title">Filtres</span>
      <button class="sidebar-clear" onclick="clearAllFilters()">✕ Tout effacer</button>
    </div>
    <div id="filter-groups">
      <!-- Généré par JS -->
    </div>
  </aside>

  <!-- MAIN -->
  <main class="main">

    <!-- STATS -->
    <div class="stats-row">
      <div class="stat-chip"><div class="stat-chip-val" id="st-articles">—</div><div class="stat-chip-lbl">Articles taggés</div></div>
      <div class="stat-chip"><div class="stat-chip-val" id="st-dispositifs">—</div><div class="stat-chip-lbl">Dispositifs collectés</div></div>
      <div class="stat-chip"><div class="stat-chip-val" id="st-cdc">—</div><div class="stat-chip-lbl">Cahiers</div></div>
      <div class="stat-chip"><div class="stat-chip-val" id="st-today">—</div><div class="stat-chip-lbl">Aujourd'hui</div></div>
    </div>

    <!-- PANEL VEILLE -->
    <div class="panel active" id="panel-veille">
      <!-- Ligne 1 : filtres de type -->
      <div class="vf-row">
        <button onclick="refreshVeille()" class="disp-refresh-btn" title="Rafraîchir la veille">↺</button>
        <div class="vf-btns">
          <button class="vf-btn active" id="vft-all"  onclick="setViewFilter('all',  this)">Tout</button>
          <button class="vf-btn"        id="vft-actu" onclick="setViewFilter('actu', this)">📰 Actualités</button>
          <button class="vf-btn"        id="vft-disp" onclick="setViewFilter('disp', this)">⭐ Dispositifs</button>
          <button class="vf-btn"        id="vft-cdc"  onclick="setViewFilter('cdc',  this)">📋 Avec CDC</button>
        </div>
        <div class="vf-right">
          <span class="result-count" id="result-count">— articles</span>
          <select class="vf-sort-select" onchange="setSortFromSelect(this)">
            <option value="date">Trier : Date</option>
            <option value="cdc">CDC en 1er</option>
            <option value="dispositif">Dispositifs d'abord</option>
          </select>
          <!-- Bouton collect avec sous-menu -->
          <div style="position:relative;" id="collect-all-wrap">
            <button id="btn-collect-all" onclick="toggleCollectMenu()"
              style="padding:5px 14px;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;border:1.5px solid var(--accent);background:var(--accent);color:var(--lime);white-space:nowrap;display:flex;align-items:center;gap:6px;">
              📥 Tout collecter <span style="font-size:9px;opacity:0.8;">▾</span>
            </button>
            <div id="collect-submenu" style="display:none;position:absolute;top:calc(100% + 6px);right:0;background:var(--surface);border:1px solid var(--border);border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,0.12);z-index:999;min-width:260px;overflow:hidden;">
              <div style="padding:8px 12px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);border-bottom:1px solid var(--border);">Choisir ce qu'on collecte</div>
              <button onclick="collectAllMissing('all')" class="collect-submenu-item">
                <span style="font-size:15px;">📥</span>
                <div><div style="font-weight:700;font-size:12px;">Tous les dispositifs</div><div style="font-size:11px;color:var(--muted);">Avec et sans CDC</div></div>
              </button>
              <button onclick="collectAllMissing('cdc')" class="collect-submenu-item" style="border-top:1px solid var(--border);">
                <span style="font-size:15px;">📋</span>
                <div><div style="font-weight:700;font-size:12px;color:#3a6000;">Dispositifs avec CDC</div><div style="font-size:11px;color:var(--muted);">Qualité supérieure — recommandé</div></div>
              </button>
              <button onclick="collectAllMissing('nocdc')" class="collect-submenu-item" style="border-top:1px solid var(--border);">
                <span style="font-size:15px;">🌐</span>
                <div><div style="font-weight:700;font-size:12px;">Dispositifs sans CDC</div><div style="font-size:11px;color:var(--muted);">Via la page web uniquement</div></div>
              </button>
            </div>
          </div>
        </div>
      </div>
      <div class="articles-list" id="articles-list">
        <div class="spinner"></div>
      </div>
    </div>

    <!-- PANEL DISPOSITIFS -->
    <div class="panel" id="panel-dispositifs">
      <!-- Barre de contrôles -->
      <div class="disp-controls">
        <button onclick="refreshDispositifs()" class="disp-refresh-btn" title="Rafraîchir les dispositifs">↺</button>
        <div class="disp-view-toggle">
          <button class="dv-btn active" id="dv-cards" onclick="setDispView('cards', this)">🗂 Bibliothèque</button>
          <button class="dv-btn"        id="dv-table" onclick="setDispView('table', this)">📊 Base de données</button>
        </div>
        <input id="disp-search" placeholder="Rechercher…" oninput="filterDispositifs()" class="disp-search-input">
        <select id="disp-filter-benef" onchange="filterDispositifs()" class="disp-filter-sel">
          <option value="">Tous bénéficiaires</option>
          <option>Collectivité</option><option>Entreprise</option><option>PME</option>
          <option>TPE</option><option>ETI</option><option>Association</option>
          <option>Start-up</option><option>ESS/Insertion</option>
          <option>Particulier</option><option>Agriculteur</option>
        </select>
        <select id="disp-filter-territoire" onchange="filterDispositifs()" class="disp-filter-sel">
          <option value="">Tous territoires</option>
          <option>National</option><option>Europe</option>
          <option>Nouvelle-Aquitaine</option><option>Occitanie</option>
          <option>Auvergne-Rhône-Alpes</option><option>Bretagne</option>
          <option>Normandie</option><option>Hauts-de-France</option>
          <option>Île-de-France</option><option>Grand Est</option>
          <option>Pays de la Loire</option><option>PACA</option>
          <option>Bourgogne-FC</option><option>Centre-Val de Loire</option>
        </select>
        <select id="disp-filter-nature" onchange="filterDispositifs()" class="disp-filter-sel">
          <option value="">Toutes natures</option>
          <option>Subvention</option><option>Prêt</option>
          <option>Avance remboursable</option><option>Garantie</option>
          <option>Crédit d'impôt</option><option>Exonération fiscale</option>
          <option>Investissement en fonds propres</option>
        </select>
        <select id="disp-filter-depot" onchange="filterDispositifs()" class="disp-filter-sel">
          <option value="">Tous dépôts</option>
          <option>Au fil de l'eau</option><option>Date</option>
          <option>Clôturé</option><option>En attente de renouvellement</option>
        </select>
        <span class="result-count" id="disp-count" style="margin-left:auto;">— dispositifs</span>
      </div>
      <!-- Vue cartes (bibliothèque) -->
      <div class="disp-grid" id="disp-grid">
        <div class="spinner"></div>
      </div>
      <!-- Vue tableau (base de données) -->
      <div id="disp-table-wrap" style="display:none;overflow-x:auto;">
        <table class="disp-table" id="disp-table">
          <thead>
            <tr>
              <th onclick="sortDispTable('titre')" class="dt-sort">Titre ↕</th>
              <th onclick="sortDispTable('guichet_financeur')" class="dt-sort">Financeur ↕</th>
              <th onclick="sortDispTable('nature')" class="dt-sort">Nature ↕</th>
              <th onclick="sortDispTable('beneficiaire')" class="dt-sort">Bénéficiaire ↕</th>
              <th onclick="sortDispTable('territoire')" class="dt-sort">Territoire ↕</th>
              <th onclick="sortDispTable('type_depot')" class="dt-sort">Dépôt ↕</th>
              <th onclick="sortDispTable('date_fermeture')" class="dt-sort">Clôture ↕</th>
              <th>Montants</th>
              <th>Objectif</th>
              <th>Dépenses éligibles</th>
              <th>Critères</th>
              <th>Points vigilance</th>
              <th onclick="sortDispTable('guichet_instructeur')" class="dt-sort">Instructeur ↕</th>
              <th>Programme EU</th>
              <th>Contact</th>
              <th style="width:80px;text-align:center;">Export</th>
            </tr>
          </thead>
          <tbody id="disp-table-body"></tbody>
        </table>
      </div>
    </div>

    <!-- PANEL CDC -->
    <div class="panel" id="panel-cdc">
      <div class="sort-row">
        <span class="result-count" id="cdc-count">— documents</span>
      </div>
      <div class="cdc-list" id="cdc-list">
        <div class="spinner"></div>
      </div>
    </div>

    <!-- PANEL JOURNAL -->
    <div class="panel" id="panel-journal">
      <div class="sort-row" style="flex-wrap:wrap;gap:8px;align-items:center;">
        <span class="result-count" id="journal-count">— éditions</span>
        <div style="flex:1"></div>
        <select id="journal-period" style="padding:5px 10px;border:1px solid var(--border);border-radius:6px;font-size:11px;background:var(--surface2);color:var(--text);outline:none;cursor:pointer;">
          <option value="7">7 derniers jours</option>
          <option value="14">14 derniers jours</option>
          <option value="30" selected>30 derniers jours</option>
          <option value="0">Tous les articles visibles</option>
        </select>
        <button id="btn-gen-journal" onclick="generateJournal()"
          style="padding:5px 16px;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;border:none;background:var(--accent);color:var(--lime);white-space:nowrap;">
          📰 Générer
        </button>
      </div>
      <!-- Vue journal courant -->
      <div id="journal-current" style="display:none;">
        <div class="journal-masthead">
          <div>
            <div class="journal-name">Sub<em>stan</em>Ciel</div>
            <div style="font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-top:2px;">Journal de Veille</div>
          </div>
          <div class="journal-meta">
            <div id="journal-edition-num" style="font-size:13px;font-weight:700;color:var(--text);">Édition #1</div>
            <div id="journal-edition-date"></div>
            <div id="journal-edition-count" style="font-size:10px;"></div>
          </div>
        </div>
        <div class="journal-edition-label">
          <span>Actualités de la veille — résumés éditoriaux</span>
          <span id="journal-page-label">Page 1</span>
        </div>
        <div class="journal-grid" id="journal-grid"></div>
        <div class="journal-page-controls">
          <button class="journal-page-btn" id="journal-prev" onclick="journalChangePage(-1)">← Précédent</button>
          <span class="journal-page-info" id="journal-page-info"></span>
          <button class="journal-page-btn" id="journal-next" onclick="journalChangePage(1)">Suivant →</button>
          <button onclick="saveJournal()" style="padding:5px 12px;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;border:1.5px solid var(--accent);background:none;color:var(--accent);">💾 Sauvegarder</button>
          <button onclick="exportJournalHTML()" style="padding:5px 12px;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;border:1.5px solid var(--border);background:var(--surface2);color:var(--muted);">⬇ HTML</button>
          <button onclick="exportJournalPDF()" style="padding:5px 12px;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;border:1.5px solid var(--border);background:var(--surface2);color:var(--muted);">🖨 PDF</button>
          <button onclick="closeJournalCurrent()" style="padding:5px 12px;border-radius:6px;font-size:11px;cursor:pointer;border:1px solid var(--border);background:var(--surface2);color:var(--muted);">✕ Fermer</button>
        </div>
      </div>
      <!-- Historique -->
      <div id="journal-hist-section">
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin:8px 0 10px;">Historique des éditions</div>
        <div class="journal-hist" id="journal-hist-list">
          <div class="spinner"></div>
        </div>
      </div>
    </div>

    <!-- PANEL PRÉ-VEILLE 360° -->
    <div class="panel" id="panel-veille360">
      <div class="sort-row" style="flex-wrap:wrap;gap:8px;">
        <span class="result-count" id="v360-sessions-count">— analyses</span>
        <input id="v360-client-input" placeholder="Nom du client / dossier…"
          style="padding:5px 10px;border:1px solid var(--border);border-radius:6px;font-size:12px;background:var(--surface2);color:var(--text);outline:none;min-width:160px;flex:1;">
        <button onclick="runV360()" id="v360-run-btn"
          style="padding:5px 14px;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;border:none;background:var(--accent);color:var(--lime);">
          🔍 Lancer une analyse
        </button>
      </div>
      <div id="v360-form" style="padding:10px 0 4px;display:flex;flex-direction:column;gap:8px;">
        <textarea id="v360-project" placeholder="Décrivez le projet CAPEX du client : porteur, nature des travaux, localisation, montant estimé, contexte…"
          style="width:100%;min-height:90px;background:var(--surface);border:1px solid var(--border);border-radius:8px;color:var(--text);padding:10px;font-size:12px;resize:vertical;font-family:inherit;box-sizing:border-box;"></textarea>
        <div id="v360-status-inline" style="font-size:11px;color:var(--muted);min-height:16px;"></div>
      </div>
      <div style="font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin:8px 0 6px;">Historique des analyses</div>
      <div id="v360-sessions-list" style="display:flex;flex-direction:column;gap:6px;">
        <div class="spinner"></div>
      </div>
    </div>
    <!-- PANEL JOURNAL -->
    <div class="panel" id="panel-journal">
      <div class="sort-row" style="flex-wrap:wrap;gap:8px;align-items:center;">
        <span class="result-count" id="journal-count">— éditions</span>
        <div style="flex:1"></div>
        <select id="journal-period" style="padding:5px 10px;border:1px solid var(--border);border-radius:6px;font-size:11px;background:var(--surface2);color:var(--text);outline:none;cursor:pointer;">
          <option value="7">7 derniers jours</option>
          <option value="14">14 derniers jours</option>
          <option value="30" selected>30 derniers jours</option>
          <option value="0">Tous les articles visibles</option>
        </select>
        <button id="btn-gen-journal" onclick="generateJournal()"
          style="padding:5px 16px;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;border:none;background:var(--accent);color:var(--lime);white-space:nowrap;">
          📰 Générer
        </button>
      </div>
      <!-- Vue journal courant -->
      <div id="journal-current" style="display:none;">
        <div class="journal-masthead">
          <div>
            <div class="journal-name">Sub<em>stan</em>Ciel</div>
            <div style="font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-top:2px;">Journal de Veille</div>
          </div>
          <div class="journal-meta">
            <div id="journal-edition-num" style="font-size:13px;font-weight:700;color:var(--text);">Édition #1</div>
            <div id="journal-edition-date"></div>
            <div id="journal-edition-count" style="font-size:10px;"></div>
          </div>
        </div>
        <div class="journal-edition-label">
          <span>Actualités de la veille — résumés éditoriaux</span>
          <span id="journal-page-label">Page 1</span>
        </div>
        <div class="journal-grid" id="journal-grid"></div>
        <div class="journal-page-controls">
          <button class="journal-page-btn" id="journal-prev" onclick="journalChangePage(-1)">← Précédent</button>
          <span class="journal-page-info" id="journal-page-info"></span>
          <button class="journal-page-btn" id="journal-next" onclick="journalChangePage(1)">Suivant →</button>
          <button onclick="saveJournal()" style="padding:5px 12px;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;border:1.5px solid var(--accent);background:none;color:var(--accent);">💾 Sauvegarder</button>
          <button onclick="exportJournalHTML()" style="padding:5px 12px;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;border:1.5px solid var(--border);background:var(--surface2);color:var(--muted);">⬇ HTML</button>
          <button onclick="exportJournalPDF()" style="padding:5px 12px;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;border:1.5px solid var(--border);background:var(--surface2);color:var(--muted);">🖨 PDF</button>
          <button onclick="closeJournalCurrent()" style="padding:5px 12px;border-radius:6px;font-size:11px;cursor:pointer;border:1px solid var(--border);background:var(--surface2);color:var(--muted);">✕ Fermer</button>
        </div>
      </div>
      <!-- Historique -->
      <div id="journal-hist-section">
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin:8px 0 10px;">Historique des éditions</div>
        <div class="journal-hist" id="journal-hist-list">
          <div class="spinner"></div>
        </div>
      </div>
    </div>

    <!-- ESPACE PROJET -->
    <div class="panel" id="panel-veille360">

      <!-- VUE LISTE DES PROJETS -->
      <div id="ep-list-view">
        <div class="ep-list-header">
          <span class="result-count" id="v360-sessions-count">— dossiers</span>
          <button onclick="openNewProjet()" class="ep-new-btn">+ Nouveau dossier</button>
        </div>
        <div id="v360-sessions-list" style="display:flex;flex-direction:column;gap:8px;margin-top:12px;">
          <div class="spinner"></div>
        </div>
      </div>

      <!-- VUE DÉTAIL D'UN PROJET -->
      <div id="ep-detail-view" style="display:none;">
        <!-- Header projet -->
        <div class="ep-header">
          <div>
            <div class="ep-client-name" id="ep-client-name">Client</div>
            <div class="ep-project-desc" id="ep-project-desc"></div>
          </div>
          <div style="display:flex;gap:8px;align-items:center;">
            <button onclick="exportProjetPptx()" class="ep-action-btn ep-pptx-btn">📊 Export PPTX</button>
            <button onclick="closeProjetDetail()" class="ep-action-btn ep-back-btn">← Retour</button>
          </div>
        </div>

        <!-- Onglets du projet -->
        <div class="ep-tabs">
          <button class="ep-tab active" id="ept-analyse" onclick="switchEpTab('analyse',this)">🔍 Analyse 360°</button>
          <button class="ep-tab" id="ept-shortlist" onclick="switchEpTab('shortlist',this)">⭐ Shortlist</button>
          <button class="ep-tab" id="ept-notes" onclick="switchEpTab('notes',this)">📝 Notes</button>
        </div>

        <!-- Volet Analyse 360° -->
        <div class="ep-pane active" id="ep-pane-analyse">
          <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;">
            <textarea id="v360-project" placeholder="Décrivez le projet : porteur, nature des travaux, localisation, montant estimé, contexte…"
              style="flex:1;min-width:280px;min-height:70px;background:var(--surface);border:1px solid var(--border);border-radius:8px;color:var(--text);padding:10px;font-size:12px;resize:vertical;font-family:inherit;box-sizing:border-box;"></textarea>
            <div style="display:flex;flex-direction:column;gap:6px;justify-content:flex-end;">
              <button onclick="runV360()" id="v360-run-btn" class="ep-action-btn" style="background:var(--accent);color:var(--lime);border:none;">🔍 Analyser</button>
            </div>
          </div>
          <div id="v360-status-inline" style="font-size:11px;color:var(--muted);min-height:14px;margin-bottom:8px;"></div>
          <div id="v360-modal-body" style="font-size:12px;line-height:1.6;"></div>
        </div>

        <!-- Volet Shortlist -->
        <div class="ep-pane" id="ep-pane-shortlist">
          <div class="ep-kanban" id="ep-kanban">
            <div class="ep-kanban-col">
              <div class="ep-kanban-title">🔵 Identifié</div>
              <div class="ep-kanban-cards" id="ep-col-identifie"></div>
            </div>
            <div class="ep-kanban-col">
              <div class="ep-kanban-title">🟡 En cours</div>
              <div class="ep-kanban-cards" id="ep-col-en_cours"></div>
            </div>
            <div class="ep-kanban-col">
              <div class="ep-kanban-title">🟢 Déposé</div>
              <div class="ep-kanban-cards" id="ep-col-depose"></div>
            </div>
          </div>
        </div>

        <!-- Volet Notes -->
        <div class="ep-pane" id="ep-pane-notes">
          <textarea id="ep-notes-area" placeholder="Notes libres sur le projet, le client, les échanges…"
            style="width:100%;min-height:300px;background:var(--surface);border:1px solid var(--border);border-radius:8px;color:var(--text);padding:14px;font-size:13px;line-height:1.7;resize:vertical;font-family:inherit;box-sizing:border-box;"
            oninput="autoSaveNotes()"></textarea>
          <div id="ep-notes-saved" style="font-size:10px;color:var(--muted);margin-top:6px;"></div>
        </div>
      </div>

      <!-- MODAL NOUVEAU PROJET -->
      <div id="ep-new-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:500;align-items:center;justify-content:center;">
        <div style="background:var(--surface);border-radius:14px;padding:28px;width:90%;max-width:520px;box-shadow:0 20px 60px rgba(0,0,0,.2);">
          <div style="font-family:'Syne',sans-serif;font-size:16px;font-weight:800;color:var(--accent);margin-bottom:16px;">Nouveau dossier client</div>
          <input id="ep-new-client" placeholder="Nom du client…" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:8px;font-size:13px;background:var(--surface2);color:var(--text);outline:none;box-sizing:border-box;margin-bottom:10px;">
          <textarea id="ep-new-desc" placeholder="Description du projet CAPEX : nature, localisation, montant estimé, porteur…" style="width:100%;min-height:100px;padding:10px;border:1px solid var(--border);border-radius:8px;font-size:13px;background:var(--surface2);color:var(--text);outline:none;resize:vertical;font-family:inherit;box-sizing:border-box;margin-bottom:16px;"></textarea>
          <div style="display:flex;gap:8px;justify-content:flex-end;">
            <button onclick="closeNewProjet()" style="padding:8px 18px;border:1px solid var(--border);border-radius:8px;background:var(--surface2);cursor:pointer;font-size:13px;">Annuler</button>
            <button onclick="createProjet()" style="padding:8px 18px;border:none;border-radius:8px;background:var(--accent);color:var(--lime);cursor:pointer;font-size:13px;font-weight:700;">Créer le dossier</button>
          </div>
        </div>
      </div>

      <!-- MODAL EMAIL CONTACT -->
      <div id="ep-email-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:500;align-items:center;justify-content:center;">
        <div style="background:var(--surface);border-radius:14px;padding:28px;width:90%;max-width:600px;box-shadow:0 20px 60px rgba(0,0,0,.2);">
          <div style="font-family:'Syne',sans-serif;font-size:15px;font-weight:800;color:var(--accent);margin-bottom:14px;">📧 Email de contact généré</div>
          <textarea id="ep-email-content" style="width:100%;min-height:220px;padding:12px;border:1px solid var(--border);border-radius:8px;font-size:12px;line-height:1.7;background:var(--surface2);color:var(--text);resize:vertical;font-family:monospace;box-sizing:border-box;"></textarea>
          <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px;">
            <button onclick="copyEmail()" style="padding:8px 18px;border:1.5px solid var(--accent);border-radius:8px;background:none;color:var(--accent);cursor:pointer;font-size:12px;font-weight:700;">📋 Copier</button>
            <button onclick="document.getElementById('ep-email-modal').style.display='none'" style="padding:8px 18px;border:1px solid var(--border);border-radius:8px;background:var(--surface2);cursor:pointer;font-size:12px;">Fermer</button>
          </div>
        </div>
      </div>

    </div>

    <!-- PANEL PACKAGES -->
    <div class="panel" id="panel-packages">
      <div class="disp-controls" style="justify-content:space-between;">
        <span id="pkg-list-count" style="font-size:11px;color:var(--muted);">— packages</span>
        <button onclick="openManualCollect()" style="background:var(--accent);color:var(--lime);border:none;border-radius:6px;padding:7px 16px;font-size:12px;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif;">➕ Nouvelle collecte</button>
      </div>
      <div id="pkg-list" style="padding:16px 20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;"><div style="color:var(--muted);font-size:12px;text-align:center;padding:40px;grid-column:1/-1;">Chargement…</div></div>
      <div id="pkg-detail" style="display:none;flex:1;flex-direction:column;overflow:hidden;">
        <div style="padding:12px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px;flex-shrink:0;">
          <button onclick="closePkgDetail()" style="background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:6px 12px;font-size:11px;cursor:pointer;font-family:'DM Sans',sans-serif;">← Retour</button>
          <span id="pkg-detail-name" style="font-family:'Syne',sans-serif;font-weight:800;font-size:15px;color:var(--accent);flex:1;"></span>
          <span id="pkg-detail-count" style="font-size:11px;color:var(--muted);"></span>
          <button onclick="exportPackageCdc()" id="pkg-cdc-btn" style="background:var(--surface2);color:var(--accent);border:1.5px solid var(--border);border-radius:6px;padding:7px 14px;font-size:12px;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif;">📎 CDCs</button>
          <button onclick="openMergeModal()" style="background:var(--surface2);color:var(--accent);border:1.5px solid var(--border);border-radius:6px;padding:7px 14px;font-size:12px;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif;">🔀 Fusionner</button>
          <button onclick="exportPackagePptx()" style="background:var(--accent);color:var(--lime);border:none;border-radius:6px;padding:7px 14px;font-size:12px;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif;">📊 Exporter PPTX</button>
          <button onclick="deleteCurrentPackage()" style="background:none;border:1.5px solid rgba(200,57,43,0.3);border-radius:6px;padding:7px 12px;font-size:12px;font-weight:700;cursor:pointer;color:#c8392b;font-family:'DM Sans',sans-serif;">🗑</button>
        </div>
        <!-- Sub-tabs -->
        <div style="display:flex;border-bottom:1px solid var(--border);flex-shrink:0;background:var(--surface2);">
          <button id="pkg-tab-disp" onclick="switchPkgTab('disp')" style="padding:9px 18px;font-size:11px;font-weight:700;border:none;cursor:pointer;font-family:'DM Sans',sans-serif;background:var(--surface);color:var(--accent);border-bottom:2px solid var(--accent);">📦 Dispositifs</button>
          <button id="pkg-tab-logs" onclick="switchPkgTab('logs')" style="padding:9px 18px;font-size:11px;font-weight:700;border:none;cursor:pointer;font-family:'DM Sans',sans-serif;background:transparent;color:var(--muted);border-bottom:2px solid transparent;">🔴 Erreurs <span id="pkg-logs-badge" style="display:none;background:#c8392b;color:#fff;border-radius:100px;padding:1px 6px;font-size:10px;margin-left:4px;"></span></button>
        </div>
        <div id="pkg-pane-disp" style="flex:1;overflow-y:auto;padding:16px 20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;"></div>
        <div id="pkg-pane-logs" style="display:none;flex:1;overflow-y:auto;padding:16px 20px;"></div>
      </div>
    </div>



  </main>
</div>

<!-- MODAL RÉSULTAT 360 -->
<div id="v360-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:9998;align-items:center;justify-content:center;">
  <div style="background:var(--surface);border-radius:12px;width:92%;max-width:920px;max-height:88vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.3);">
    <div style="padding:14px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;background:var(--surface2);border-radius:12px 12px 0 0;">
      <div style="font-family:'Syne',sans-serif;font-size:14px;font-weight:800;color:var(--accent);" id="v360-modal-title">Analyse 360°</div>
      <button onclick="document.getElementById('v360-modal').style.display='none'"
        style="background:none;border:1px solid var(--border);border-radius:6px;width:28px;height:28px;cursor:pointer;font-size:14px;color:var(--muted);">✕</button>
    </div>
    <div style="flex:1;overflow-y:auto;padding:16px 20px;font-size:12px;line-height:1.6;color:var(--text);" id="v360-modal-body"></div>
  </div>
</div>

<!-- MODAL DISPOSITIF -->
<div class="modal-overlay" id="modal" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="modal-title" id="modal-title">Dispositif</div>
    <div class="modal-grid" id="modal-body"></div>
    <div class="modal-footer">
      <button class="modal-close" onclick="closeModal()">Fermer</button>
      <button class="modal-pptx" id="modal-pptx-btn" onclick="exportDispPptx()">📊 Exporter PPTX</button>
    </div>
  </div>
</div>

<!-- MODAL COLLECTE MANUELLE -->
<div id="manual-collect-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:500;align-items:center;justify-content:center;">
  <div style="background:var(--surface);border-radius:16px;width:720px;max-width:96vw;max-height:92vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(26,60,46,0.22);overflow:hidden;">

    <!-- Header -->
    <div style="background:var(--accent);padding:18px 24px;display:flex;align-items:center;gap:14px;flex-shrink:0;">
      <div style="width:36px;height:36px;background:var(--lime);border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;">➕</div>
      <div>
        <div style="font-family:'Syne',sans-serif;font-size:15px;font-weight:800;color:#fff;letter-spacing:-0.3px;">Collecte manuelle</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:1px;">Ajoutez un dispositif depuis un lien ou un fichier Excel</div>
      </div>
      <button onclick="closeManualCollect()" style="margin-left:auto;background:rgba(255,255,255,0.1);border:none;border-radius:8px;width:32px;height:32px;cursor:pointer;color:rgba(255,255,255,0.7);font-size:16px;display:flex;align-items:center;justify-content:center;">✕</button>
    </div>

    <!-- Tabs -->
    <div style="display:flex;border-bottom:1px solid var(--border);flex-shrink:0;background:var(--surface2);">
      <button id="mc-tab-url" onclick="switchMcTab('url')" style="flex:1;padding:11px 0;font-size:12px;font-weight:700;border:none;cursor:pointer;font-family:'DM Sans',sans-serif;background:var(--surface);color:var(--accent);border-bottom:2px solid var(--accent);">🔗 Lien</button>
      <button id="mc-tab-cdc" onclick="switchMcTab('cdc')" style="flex:1;padding:11px 0;font-size:12px;font-weight:700;border:none;cursor:pointer;font-family:'DM Sans',sans-serif;background:transparent;color:var(--muted);border-bottom:2px solid transparent;">📄 CDC</button>
      <button id="mc-tab-excel" onclick="switchMcTab('excel')" style="flex:1;padding:11px 0;font-size:12px;font-weight:700;border:none;cursor:pointer;font-family:'DM Sans',sans-serif;background:transparent;color:var(--muted);border-bottom:2px solid transparent;">📊 Excel (bundle)</button>
      <button id="mc-tab-text" onclick="switchMcTab('text')" style="flex:1;padding:11px 0;font-size:12px;font-weight:700;border:none;cursor:pointer;font-family:'DM Sans',sans-serif;background:transparent;color:var(--muted);border-bottom:2px solid transparent;">✏️ Texte</button>
    </div>

    <!-- TAB : Lien unique -->
    <div id="mc-pane-url" style="display:flex;flex-direction:column;flex:1;overflow:hidden;">
      <div style="padding:16px 24px 12px;border-bottom:1px solid var(--border);flex-shrink:0;">
        <div style="display:flex;gap:10px;">
          <input id="mc-url-input" type="url" placeholder="https://…" style="flex:1;background:var(--surface2);border:1.5px solid var(--border);border-radius:8px;padding:10px 14px;font-size:13px;font-family:'DM Sans',sans-serif;color:var(--text);outline:none;" onkeydown="if(event.key==='Enter') runManualCollect()">
          <button id="mc-run-btn" onclick="runManualCollect()" style="background:var(--accent);color:var(--lime);border:none;border-radius:8px;padding:10px 20px;font-size:12px;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif;white-space:nowrap;">Analyser</button>
        </div>
        <div id="mc-cdc-status" style="margin-top:8px;font-size:11px;color:var(--muted);min-height:16px;"></div>
      </div>
      <div id="mc-result-area" style="padding:16px 24px;flex:1;overflow-y:auto;min-height:120px;">
        <div style="text-align:center;color:var(--muted);font-size:12px;padding:32px 0;">Entrez une URL puis cliquez sur Analyser.</div>
      </div>
      <div id="mc-footer" style="display:none;padding:13px 24px;border-top:1px solid var(--border);display:none;gap:9px;justify-content:flex-end;flex-shrink:0;">
        <button onclick="closeManualCollect()" style="background:var(--surface2);border:1px solid var(--border);border-radius:7px;padding:8px 16px;font-size:12px;cursor:pointer;font-family:'DM Sans',sans-serif;">Annuler</button>
        <button id="mc-save-btn" onclick="saveManualCollect()" style="background:var(--accent);color:var(--lime);border:none;border-radius:7px;padding:8px 18px;font-size:12px;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif;">💾 Sauvegarder</button>
      </div>
    </div>


    <!-- TAB : CDC (Cahier des charges PDF) -->
    <div id="mc-pane-cdc" style="display:none;flex-direction:column;flex:1;overflow:hidden;">
      <div style="padding:16px 24px 12px;border-bottom:1px solid var(--border);flex-shrink:0;">
        <div style="font-size:11px;color:var(--muted);margin-bottom:12px;">Uploadez directement un CDC (PDF/Word) — l'IA analyse le document pour extraire les 19 champs.</div>
        <div style="display:flex;gap:10px;margin-bottom:10px;">
          <input id="mc-cdc-url-input" type="url" placeholder="URL source du dispositif (optionnel)" style="flex:1;background:var(--surface2);border:1.5px solid var(--border);border-radius:8px;padding:9px 14px;font-size:12px;font-family:'DM Sans',sans-serif;color:var(--text);outline:none;">
        </div>
        <div id="mc-cdc-dropzone" onclick="document.getElementById('mc-cdc-file').click()" style="border:2px dashed var(--border);border-radius:10px;padding:24px 20px;text-align:center;cursor:pointer;transition:all 0.18s;">
          <div style="font-size:26px;margin-bottom:8px;">📄</div>
          <div style="font-size:13px;font-weight:700;color:var(--accent);margin-bottom:4px;">Cliquez ou glissez un fichier PDF / Word</div>
          <div style="font-size:11px;color:var(--muted);">.pdf · .doc · .docx — max 5 Mo</div>
          <input id="mc-cdc-file" type="file" accept=".pdf,.doc,.docx" style="display:none;" onchange="onCdcFileSelected(this)">
        </div>
        <div id="mc-cdc-file-name" style="margin-top:8px;font-size:11px;color:var(--accent);font-weight:600;text-align:center;display:none;"></div>
      </div>
      <div id="mc-cdc-result-area" style="padding:16px 24px;flex:1;overflow-y:auto;min-height:120px;">
        <div style="text-align:center;color:var(--muted);font-size:12px;padding:32px 0;">Importez un CDC pour démarrer l'analyse.</div>
      </div>
      <div style="padding:13px 24px;border-top:1px solid var(--border);display:flex;gap:9px;justify-content:flex-end;flex-shrink:0;">
        <button onclick="closeManualCollect()" style="background:var(--surface2);border:1px solid var(--border);border-radius:7px;padding:8px 16px;font-size:12px;cursor:pointer;font-family:'DM Sans',sans-serif;">Annuler</button>
        <button id="mc-cdc-run-btn" onclick="runCdcCollect()" style="background:var(--accent);color:var(--lime);border:none;border-radius:7px;padding:8px 18px;font-size:12px;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif;" disabled>Analyser le CDC</button>
      </div>
      <div id="mc-cdc-footer" style="display:none;padding:13px 24px;border-top:1px solid var(--border);display:none;gap:9px;justify-content:flex-end;flex-shrink:0;">
        <button onclick="closeManualCollect()" style="background:var(--surface2);border:1px solid var(--border);border-radius:7px;padding:8px 16px;font-size:12px;cursor:pointer;font-family:'DM Sans',sans-serif;">Annuler</button>
        <button id="mc-cdc-save-btn" onclick="saveCdcCollect()" style="background:var(--accent);color:var(--lime);border:none;border-radius:7px;padding:8px 18px;font-size:12px;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif;">Sauvegarder</button>
      </div>
    </div>

    <!-- TAB : Fichier Excel -->
    <div id="mc-pane-excel" style="display:none;flex-direction:column;flex:1;overflow:hidden;">
      <div style="padding:18px 24px;flex-shrink:0;border-bottom:1px solid var(--border);">
        <!-- Drop zone -->
        <div id="mc-dropzone" onclick="document.getElementById('mc-file-input').click()" style="border:2px dashed var(--border);border-radius:10px;padding:28px 20px;text-align:center;cursor:pointer;transition:all 0.18s;">
          <div style="font-size:28px;margin-bottom:8px;">📊</div>
          <div style="font-size:13px;font-weight:700;color:var(--accent);margin-bottom:4px;">Cliquez ou glissez un fichier .xlsx</div>
          <div style="font-size:11px;color:var(--muted);">URLs en colonne A · Feuille 1 · Max 30 liens</div>
          <input id="mc-file-input" type="file" accept=".xlsx,.xls" style="display:none;" onchange="onExcelFileSelected(this)">
        </div>
        <div id="mc-file-name" style="margin-top:10px;font-size:11px;color:var(--accent);font-weight:600;text-align:center;display:none;"></div>

        <!-- Package option -->
        <div style="margin-top:16px;background:var(--surface2);border:1px solid var(--border);border-radius:9px;padding:13px 16px;">
          <label style="display:flex;align-items:center;gap:10px;cursor:pointer;user-select:none;">
            <input type="checkbox" id="mc-pkg-check" onchange="togglePkgName()" style="width:16px;height:16px;accent-color:var(--accent);">
            <span style="font-size:12px;font-weight:600;color:var(--text);">Regrouper dans un Package</span>
            <span style="font-size:11px;color:var(--muted);">— retrouvez tous ces dispositifs ensemble</span>
          </label>
          <div id="mc-pkg-name-wrap" style="display:none;margin-top:10px;">
            <input id="mc-pkg-name" type="text" placeholder="Nom du package (ex: ESS Bretagne 2025)" style="width:100%;background:var(--surface);border:1.5px solid var(--border);border-radius:7px;padding:9px 13px;font-size:12px;font-family:'DM Sans',sans-serif;color:var(--text);outline:none;">
          </div>
        </div>
      </div>

      <!-- Progress / results -->
      <div id="mc-batch-area" style="padding:16px 24px;flex:1;overflow-y:auto;min-height:100px;">
        <div style="text-align:center;color:var(--muted);font-size:12px;padding:28px 0;">Importez un fichier Excel pour démarrer la collecte.</div>
      </div>

      <div style="padding:13px 24px;border-top:1px solid var(--border);display:flex;gap:9px;justify-content:flex-end;flex-shrink:0;">
        <button onclick="closeManualCollect()" style="background:var(--surface2);border:1px solid var(--border);border-radius:7px;padding:8px 16px;font-size:12px;cursor:pointer;font-family:'DM Sans',sans-serif;">Annuler</button>
        <button id="mc-batch-btn" onclick="runBatchCollect()" style="background:var(--accent);color:var(--lime);border:none;border-radius:7px;padding:8px 18px;font-size:12px;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif;" disabled>🚀 Lancer la collecte</button>
      </div>
    </div>

    <!-- TAB : Texte / Scrape manuel -->
    <div id="mc-pane-text" style="display:none;flex-direction:column;flex:1;overflow:hidden;">
      <div style="padding:14px 24px 12px;border-bottom:1px solid var(--border);flex-shrink:0;">
        <div style="font-size:11px;color:var(--muted);margin-bottom:10px;">Collez le contenu texte d un dispositif — utile pour les sites JS ou les pages inaccessibles au scraping.</div>
        <input id="mc-text-url" type="url" placeholder="URL source (optionnel)" style="width:100%;background:var(--surface2);border:1.5px solid var(--border);border-radius:8px;padding:9px 14px;font-size:12px;font-family:'DM Sans',sans-serif;color:var(--text);outline:none;margin-bottom:10px;">
        <textarea id="mc-text-area" placeholder="Collez ici le contenu complet de la page (texte brut, copier-coller depuis le navigateur)…" style="width:100%;height:160px;background:var(--surface2);border:1.5px solid var(--border);border-radius:8px;padding:10px 14px;font-size:12px;font-family:'DM Sans',sans-serif;color:var(--text);outline:none;resize:vertical;box-sizing:border-box;"></textarea>
      </div>
      <div id="mc-text-result" style="padding:16px 24px;flex:1;overflow-y:auto;min-height:80px;">
        <div style="text-align:center;color:var(--muted);font-size:12px;padding:20px 0;">Collez du texte puis cliquez sur Analyser.</div>
      </div>
      <div style="padding:13px 24px;border-top:1px solid var(--border);display:flex;gap:9px;justify-content:flex-end;flex-shrink:0;">
        <button onclick="closeManualCollect()" style="background:var(--surface2);border:1px solid var(--border);border-radius:7px;padding:8px 16px;font-size:12px;cursor:pointer;font-family:'DM Sans',sans-serif;">Annuler</button>
        <button id="mc-text-run-btn" onclick="runTextCollect()" style="background:var(--accent);color:var(--lime);border:none;border-radius:7px;padding:8px 18px;font-size:12px;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif;">Analyser</button>
      </div>
      <div id="mc-text-footer" style="display:none;padding:13px 24px;border-top:1px solid var(--border);display:none;gap:9px;justify-content:flex-end;flex-shrink:0;">
        <button onclick="closeManualCollect()" style="background:var(--surface2);border:1px solid var(--border);border-radius:7px;padding:8px 16px;font-size:12px;cursor:pointer;font-family:'DM Sans',sans-serif;">Annuler</button>
        <button id="mc-text-save-btn" onclick="saveTextCollect()" style="background:var(--accent);color:var(--lime);border:none;border-radius:7px;padding:8px 18px;font-size:12px;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif;">Sauvegarder</button>
      </div>
    </div>

  </div>
</div>
<!-- MODAL FUSION PACKAGES -->
<div id="merge-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.55);z-index:600;align-items:center;justify-content:center;">
  <div style="background:var(--surface);border-radius:14px;width:460px;max-width:95vw;box-shadow:0 16px 48px rgba(26,60,46,0.18);overflow:hidden;">
    <div style="background:var(--accent);padding:16px 20px;display:flex;align-items:center;gap:12px;">
      <div style="width:32px;height:32px;background:var(--lime);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;">🔀</div>
      <div>
        <div style="font-weight:800;font-size:14px;color:#fff;">Fusionner avec un autre package</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:1px;">Les dispositifs seront regroupés dans un nouveau package</div>
      </div>
      <button onclick="closeMergeModal()" style="margin-left:auto;background:rgba(255,255,255,0.1);border:none;border-radius:6px;width:28px;height:28px;cursor:pointer;color:rgba(255,255,255,0.7);font-size:15px;">✕</button>
    </div>
    <div style="padding:20px;">
      <div style="font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;">Package à fusionner avec</div>
      <select id="merge-target-select" style="width:100%;background:var(--surface2);border:1.5px solid var(--border);border-radius:8px;padding:10px 12px;font-size:13px;font-family:'DM Sans',sans-serif;color:var(--text);outline:none;"></select>
      <div style="margin-top:14px;">
        <div style="font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;">Nom du package fusionné</div>
        <input id="merge-name-input" type="text" placeholder="Nom du nouveau package…" style="width:100%;background:var(--surface2);border:1.5px solid var(--border);border-radius:8px;padding:10px 12px;font-size:13px;font-family:'DM Sans',sans-serif;color:var(--text);outline:none;">
      </div>
      <div style="margin-top:10px;padding:10px 12px;background:var(--lime-bg);border-radius:8px;font-size:11px;color:var(--accent);">
        ℹ️ Les deux packages sources seront supprimés après fusion. Les dispositifs sont fusionnés sans doublons.
      </div>
    </div>
    <div style="padding:12px 20px;border-top:1px solid var(--border);display:flex;gap:9px;justify-content:flex-end;">
      <button onclick="closeMergeModal()" style="background:var(--surface2);border:1px solid var(--border);border-radius:7px;padding:8px 16px;font-size:12px;cursor:pointer;font-family:'DM Sans',sans-serif;">Annuler</button>
      <button onclick="confirmMerge()" id="merge-confirm-btn" style="background:var(--accent);color:var(--lime);border:none;border-radius:7px;padding:8px 18px;font-size:12px;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif;">Fusionner</button>
    </div>
  </div>
</div>

<!-- TOAST -->
<div class="toast" id="toast"></div>

<script>
const API = '';

// ── STATE ────────────────────────────────────────────────────────────
let allArticles = [];
let allDispositifs = [];
let activeTab = 'veille';
let sortMode = 'date';
let searchQ = '';
let currentDispId = null;

// Tag filters : { groupKey: { logic: 'OR'|'AND', active: Set } }
const filterState = {};

// ── TAG BANK ─────────────────────────────────────────────────────────
const TAG_GROUPS = [
  { key: 'ref',     label: '⭐ Type',     tags: ['⭐ Dispositif', '⭐ Actualité'] },
  { key: 'qui',     label: '👥 QUI',      tags: ['Association','Collectivité','Entreprise','PME','TPE','ETI','GE','Start-up','Salariés','SENIORS','Jeunesse','ESS/Insertion','Lauréats','CSE','DRH','Etat','Union européenne'] },
  { key: 'quoi',    label: '🏭 QUOI',     tags: ['Agriculture','Alimentation durable','Artisanat/Commerce','Industrie','Industrie agroalimentaire','Mer / Littoral / Pêche / Aquaculture','Logement / Bâtiment / Construction durable','Mobilité','Tourisme','Thermalisme','Culture','Culture / Audiovisuel','Sport','Numérique','Numérique responsable / IA / Data','Énergie / Décarbonation / Sobriété','Biogaz biomasse','Sylviculture','Gestion du littoral','habitat inclusif','Médico-social'] },
  { key: 'que',     label: '🎯 QUE',      tags: ['Transition écologique','Transition énergétique','Adaptation au changement climatique','Biodiversité','Environnement','développement durable','Économie circulaire / Déchet','Innovation','Recherche','Inclusion sociale','cohésion sociale','Santé','Emploi / Formation','Formation','Education','Entrepreneuriat','Développement économique','Développement territorial','Aménagement du territoire','Politique culturelle','Sobriété foncière','Renaturation','Résilience agricole','Catastrophes naturelles','Cybersécurité','Sécurité / Défense / Souveraineté','Réforme / Réglementation','Dialogue social','Sensibilisation','Tendance de fond'] },
  { key: 'ou',      label: '🗺 OÙ',       tags: ['National','Europe','Union européenne','Régions','Auvergne-Rhône-Alpes','Bourgogne-Franche-Comté','Bretagne','Centre-Val de Loire','Corse','Grand Est','Hauts-de-France','Île-de-France','Normandie','Nouvelle-Aquitaine','Occitanie','Pays de la Loire','Sud - PACA','Guadeloupe','Guyane','La Réunion','Martinique','Mayotte','Vendée','Hérault','Italie','Périgord','QPV'] },
  { key: 'comment', label: '💰 COMMENT',  tags: ['AAP','AMI','AO','ADEME','Agence de l eau','Banque des territoires','Bpifrance','Caisse des dépôts','ANR','Aract','Dares','DDETS','DREETS','CNSA','CRESS','DILCRAH','FDVA','FEADER','FEDER','FSE','FSE+','France 2030','fonds chaleur','Financement régional','Subvention','Prêt','Avance remboursable','Crédit d impôt','Credit-bail','Fonds propres','Investissement','Investissement public','PTCE','LEADER','ALCOTRA','ODDS','CARSAT','FEAMPA','Fonds Barnier'] },
  { key: 'quand',   label: '📅 QUAND',    tags: ['En continu','En expérimentation','PLF 2026','Clôture 2026','Clôture 2027','Clôture 2028','Clôture août 2026','Clôture avril 2026','Clôture décembre 2025','Clôture décembre 2026','Clôture février 2026','Clôture janvier 2026','Clôture juillet 2026','Clôture juin 2026','Clôture mai 2026','Clôture mars 2026','Clôture novembre 2026','Clôture octobre 2026','Clôture septembre 2026'] },
];

// Init filter state
TAG_GROUPS.forEach(g => {
  filterState[g.key] = { logic: 'OR', active: new Set() };
});

// ── INIT ─────────────────────────────────────────────────────────────

function openCDC(btn) {
  var url = decodeURIComponent(btn.getAttribute('data-url') || '');
  if (url) window.open(url, '_blank');
}

function collectFromVeille(e) {
  e.stopPropagation(); e.preventDefault();
  var btn = e.currentTarget;
  var url   = decodeURIComponent(btn.getAttribute('data-url') || '');
  var title = decodeURIComponent(btn.getAttribute('data-title') || '');
  var artId = btn.getAttribute('data-id');
  var pdfUrl = decodeURIComponent(btn.getAttribute('data-pdf') || '');
  btn.disabled = true;
  btn.innerHTML = '<span class="collect-icon">⏳</span> Collecte…';
  const ctrl = new AbortController();
  const tid = setTimeout(() => ctrl.abort(), 28000);
  fetch(API + '/api/collect', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({url:url, title:title, id:parseInt(artId)||0, pdf_url:pdfUrl}),
    signal: ctrl.signal
  }).then(function(r) {
    clearTimeout(tid);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }).then(function(d) {
    if (d.status==='duplicate') {
      btn.innerHTML = '✓ Déjà collecté';
      btn.style.cssText='background:#e8f5b0;color:#3a6020;border-color:#3a6020';
    } else if (d.error) {
      btn.innerHTML = '⚠ ' + (d.error.length < 60 ? d.error : 'Erreur — voir console');
      btn.disabled = false;
      console.error('Collect error:', d.error);
    } else {
      // Sauvegarder dans la base
      return fetch(API+'/api/dispositifs',{
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(d)
      }).then(function(r2){ return r2.json(); }).then(function(d2){
        if (d2.status==='duplicate') {
          btn.innerHTML = '✓ Déjà collecté';
          btn.style.cssText='background:#e8f5b0;color:#3a6020;border-color:#3a6020';
        } else {
          btn.innerHTML = '<span class="abtn-collected">✓ Collecté</span>';
          btn.style.cssText = '';
          btn.className = 'abtn abtn-collected';
          btn.disabled = true;
          // Mettre à jour le Set en mémoire immédiatement
          if (url) collectedUrls.add(url.toLowerCase());
          loadDispositifs();
          showToast('Dispositif ajouté à la base !');
        }
      });
    }
  }).catch(function(){ btn.innerHTML='⚠ Erreur réseau'; btn.disabled=false; });
}
// ── JOURNAL ───────────────────────────────────────────────────────────
var journalSummaries = [];
var journalPage = 0;
var journalPageSize = 20;
var journalCurrentId = null;

// ── JOURNAL ───────────────────────────────────────────────────────────
var journalSummaries = [];
var journalPage = 0;
var journalPageSize = 20;
var journalCurrentId = null;

async function loadJournalHistory() {
  var list = document.getElementById('journal-hist-list');
  try {
    var res = await fetch(API + '/api/journal');
    var editions = await res.json();
    document.getElementById('journal-count').textContent = editions.length + ' edition' + (editions.length > 1 ? 's' : '');
    if (!editions.length) {
      list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📰</div><div class="empty-state-title">Aucune édition</div><p>Générez votre première édition du journal.</p></div>';
      return;
    }
    list.innerHTML = editions.map(function(e) {
      var d = e.edition_date || e.created_at.slice(0,10);
      return '<div class="journal-hist-item" data-jid="' + e.id + '" onclick="loadJournalEditionById(this)">' +
        '<div style="font-size:22px;">📰</div>' +
        '<div class="journal-hist-title">' + (e.title || 'Journal SubstanCiel') + '</div>' +
        '<div class="journal-hist-meta">' + d + '</div>' +
        '<button data-jid="' + e.id + '" onclick="deleteJournalEditionById(event,this)" style="background:none;border:none;cursor:pointer;color:var(--muted);font-size:14px;padding:4px;">✕</button>' +
        '</div>';
    }).join('');
  } catch(e) {
    list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠️</div><div class="empty-state-title">Erreur</div></div>';
  }
}

async function loadJournalEdition(id) {
  try {
    var res = await fetch(API + '/api/journal/' + id);
    var data = await res.json();
    var sums = Array.isArray(data.summaries) ? data.summaries : JSON.parse(data.summaries || '[]');
    journalSummaries = sums;
    journalPage = 0;
    journalCurrentId = id;
    var num = id;
    document.getElementById('journal-edition-num').textContent = 'Edition #' + num;
    document.getElementById('journal-edition-date').textContent = data.edition_date || data.created_at.slice(0,10);
    document.getElementById('journal-edition-count').textContent = sums.length + ' articles résumés';
    renderJournalPage();
    document.getElementById('journal-current').style.display = 'block';
    document.getElementById('journal-hist-section').style.display = 'none';
  } catch(e) { showToast('Erreur chargement édition'); }
}

function renderJournalPage() {
  var start = journalPage * journalPageSize;
  var page  = journalSummaries.slice(start, start + journalPageSize);
  var totalPages = Math.ceil(journalSummaries.length / journalPageSize);
  document.getElementById('journal-page-label').textContent = 'Page ' + (journalPage + 1) + ' / ' + totalPages;
  document.getElementById('journal-page-info').textContent = (start+1) + '-' + Math.min(start+journalPageSize, journalSummaries.length) + ' sur ' + journalSummaries.length;
  document.getElementById('journal-prev').disabled = journalPage === 0;
  document.getElementById('journal-next').disabled = journalPage >= totalPages - 1;
  var grid = document.getElementById('journal-grid');
  grid.innerHTML = page.map(function(s) {
    var imp = s.importance === 'haute' ? ' haute' : '';
    var dateStr = s.date ? s.date.slice(5).replace('-','/') : '';
    return '<div class="journal-card' + imp + '">' +
      '<div class="journal-card-cat">' + (s.category || 'Actualité') + '</div>' +
      '<div class="journal-card-title">' + s.title + '</div>' +
      '<div class="journal-card-summary">' + (s.summary || '') + '</div>' +
      '<div class="journal-card-footer">' +
        '<span class="journal-card-source">' + (s.source || '') + '</span>' +
        '<span>' + dateStr + '</span>' +
        (s.url ? '<a class="journal-card-link" href="' + encodeURI(s.url) + '" target="_blank" onclick="event.stopPropagation()">→</a>' : '') +
      '</div>' +
      '</div>';
  }).join('');
}

function journalChangePage(delta) {
  var totalPages = Math.ceil(journalSummaries.length / journalPageSize);
  journalPage = Math.max(0, Math.min(journalPage + delta, totalPages - 1));
  renderJournalPage();
  document.getElementById('journal-page-label').scrollIntoView({behavior:'smooth', block:'nearest'});
}

// Override journalPage function name conflict — rename onclick calls
// The onclick uses journalPage(-1) — rename JS function
function closeJournalCurrent() {
  document.getElementById('journal-current').style.display = 'none';
  document.getElementById('journal-hist-section').style.display = 'block';
  journalCurrentId = null;
}

async function saveJournal() {
  if (!journalSummaries.length) return;
  var today = new Date().toLocaleDateString('fr-FR');
  var title = 'Journal SubstanCiel — ' + today;
  try {
    var res = await fetch(API + '/api/journal', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({title: title, summaries: journalSummaries})
    });
    var data = await res.json();
    journalCurrentId = data.id;
    showToast('Edition sauvegardée !');
    loadJournalHistory();
  } catch(e) { showToast('Erreur sauvegarde'); }
}

async function deleteJournalEdition(e, id) {
  e.stopPropagation();
  await fetch(API + '/api/journal/' + id, {method: 'DELETE'});
  loadJournalHistory();
}

function exportJournalHTML() {
  if (!journalSummaries.length) { showToast('Aucune edition a exporter'); return; }
  var today = new Date().toLocaleDateString('fr-FR');
  var edNum = document.getElementById('journal-edition-num').textContent;
  var cards = journalSummaries.map(function(s) {
    var imp = s.importance === 'haute' ? 'border-top:3px solid #1a3c2e;' : 'border-top:3px solid #ddd;';
    var dateStr = s.date ? s.date.slice(5).replace('-','/') : '';
    return '<div style="background:#fff;border:1px solid #e0e0e0;border-radius:10px;padding:16px;display:flex;flex-direction:column;gap:8px;break-inside:avoid;' + imp + '">' +
      '<div style="font-size:9px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#888;">' + (s.category || 'Actualite') + '</div>' +
      '<div style="font-family:Georgia,serif;font-weight:700;font-size:13px;line-height:1.3;color:#111;">' + s.title + '</div>' +
      '<div style="font-size:12px;color:#444;line-height:1.65;flex:1;">' + (s.summary || '') + '</div>' +
      '<div style="display:flex;justify-content:space-between;font-size:10px;color:#aaa;border-top:1px solid #eee;padding-top:6px;margin-top:4px;">' +
        '<span style="font-weight:600;">' + (s.source||'') + '</span>' +
        '<span>' + dateStr + '</span>' +
        (s.url ? '<a href="' + s.url + '" style="color:#1a3c2e;font-weight:700;text-decoration:none;">Lire &rarr;</a>' : '') +
      '</div></div>';
  }).join('');
  var html = '<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">' +
    '<title>Journal SubstanCiel — ' + today + '</title>' +
    '<style>body{font-family:Georgia,serif;background:#faf8f4;margin:0;padding:32px;}' +
    '.masthead{border-bottom:3px solid #1a3c2e;padding-bottom:16px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:flex-end;}' +
    '.name{font-size:2.4rem;font-weight:900;color:#1a3c2e;letter-spacing:-.03em;line-height:1;}' +
    '.name em{font-style:italic;color:#7ab200;}' +
    '.meta{font-size:11px;color:#888;text-align:right;line-height:1.6;}' +
    '.divider{font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#aaa;border-top:1px solid #ddd;border-bottom:1px solid #ddd;padding:5px 0;margin-bottom:16px;}' +
    '.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;}' +
    '@media print{body{padding:16px;}.grid{grid-template-columns:repeat(3,1fr);}}</style></head>' +
    '<body>' +
    '<div class="masthead"><div><div class="name">Sub<em>stan</em>Ciel</div><div style="font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#aaa;margin-top:2px;">Journal de Veille</div></div>' +
    '<div class="meta"><div style="font-size:13px;font-weight:700;color:#111;">' + edNum + '</div><div>' + today + '</div><div style="font-size:10px;">' + journalSummaries.length + ' articles</div></div></div>' +
    '<div class="divider"><span>Actualites de la veille — resumes editoriaux</span></div>' +
    '<div class="grid">' + cards + '</div>' +
    '</body></html>';
  var blob = new Blob([html], {type: 'text/html;charset=utf-8'});
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'journal-substanciel-' + today.replace(/\//g, '-') + '.html';
  a.click();
  showToast('Journal exporté !');
}

function exportJournalPDF() {
  if (!journalSummaries.length) { showToast('Aucune edition a exporter'); return; }
  var today = new Date().toLocaleDateString('fr-FR');
  var edNum = document.getElementById('journal-edition-num').textContent;
  var cards = journalSummaries.map(function(s) {
    var imp = s.importance === 'haute' ? 'border-top:3px solid #1a3c2e;' : 'border-top:3px solid #ddd;';
    var dateStr = s.date ? s.date.slice(5).replace('-','/') : '';
    return '<div style="background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:14px;display:flex;flex-direction:column;gap:7px;break-inside:avoid;margin-bottom:12px;' + imp + '">' +
      '<div style="font-size:8px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#999;">' + (s.category || 'Actualite') + '</div>' +
      '<div style="font-family:Georgia,serif;font-weight:700;font-size:12px;line-height:1.3;color:#111;">' + s.title + '</div>' +
      '<div style="font-size:11px;color:#444;line-height:1.6;">' + (s.summary || '') + '</div>' +
      '<div style="display:flex;justify-content:space-between;font-size:9px;color:#aaa;border-top:1px solid #eee;padding-top:5px;">' +
        '<span style="font-weight:600;">' + (s.source||'') + '</span>' +
        '<span>' + dateStr + '</span>' +
      '</div></div>';
  }).join('');
  var html = '<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><title>Journal SubstanCiel</title>' +
    '<style>*{box-sizing:border-box;}body{font-family:Georgia,serif;background:#fff;margin:0;padding:20px 28px;color:#111;}' +
    '.masthead{border-bottom:3px solid #1a3c2e;padding-bottom:12px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:flex-end;}' +
    '.name{font-size:2rem;font-weight:900;color:#1a3c2e;letter-spacing:-.03em;line-height:1;}' +
    '.name em{font-style:italic;color:#7ab200;}' +
    '.divider{font-size:9px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#aaa;border-top:1px solid #ddd;border-bottom:1px solid #ddd;padding:4px 0;margin-bottom:14px;display:flex;justify-content:space-between;}' +
    '.grid{columns:3;column-gap:12px;}' +
    '@media print{@page{margin:14mm;}body{padding:0;}.grid{columns:3;}}</style></head>' +
    '<body>' +
    '<div class="masthead"><div><div class="name">Sub<em>stan</em>Ciel</div><div style="font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#aaa;margin-top:2px;">Journal de Veille</div></div>' +
    '<div style="font-size:11px;color:#888;text-align:right;line-height:1.6;"><div style="font-size:12px;font-weight:700;color:#111;">' + edNum + '</div><div>' + today + '</div><div style="font-size:9px;">' + journalSummaries.length + ' articles</div></div></div>' +
    '<div class="divider"><span>Actualites de la veille</span><span>' + today + '</span></div>' +
    '<div class="grid">' + cards + '</div>' +
    '</body></html>';
  var w = window.open('', '_blank');
  w.document.write(html);
  w.document.close();
  w.focus();
  setTimeout(function(){ w.print(); }, 600);
}

async function generateJournal() {
  var btn = document.getElementById('btn-gen-journal');
  btn.disabled = true; btn.textContent = '⏳ Génération...';

  var acts;
  if (journalManualIds.size > 0) {
    // Utiliser la sélection manuelle (boutons 📰 cliqués)
    acts = allArticles.filter(function(a){ return journalManualIds.has(a.id); }).slice(0, 24);
    journalManualIds.clear();
    document.querySelectorAll('.abtn-journal.added').forEach(function(b){ b.classList.remove('added'); b.title='Ajouter au prochain journal'; });
    var genBtn = document.getElementById('btn-gen-journal');
    if (genBtn) genBtn.textContent = '📰 Générer';
  } else {
    // Filtrer par période
    var periodDays = parseInt(document.getElementById('journal-period').value) || 0;
    var cutoff = periodDays > 0 ? new Date(Date.now() - periodDays * 86400000) : null;
    acts = allArticles.filter(function(a) {
      var tags = Array.isArray(a.tags) ? a.tags : JSON.parse(a.tags || '[]');
      if (tags.indexOf('⭐ Actualité') < 0) return false;
      if (cutoff && a.scraped_at && new Date(a.scraped_at) < cutoff) return false;
      return true;
    }).slice(0, 24);
  }

  if (!acts.length) {
    showToast('Aucune actualité disponible'); btn.disabled=false; btn.textContent='📰 Générer une édition'; return;
  }
  try {
    var res = await fetch(API + '/api/journal/summarize', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({articles: acts})
    });
    var data = await res.json();
    if (data.error) throw new Error(data.error);
    journalSummaries = data.summaries;
    journalPage = 0;
    journalCurrentId = null;
    var today = new Date().toLocaleDateString('fr-FR');
    document.getElementById('journal-edition-num').textContent = 'Nouvelle édition';
    document.getElementById('journal-edition-date').textContent = today;
    document.getElementById('journal-edition-count').textContent = journalSummaries.length + ' articles résumés';
    renderJournalPage();
    document.getElementById('journal-current').style.display = 'block';
    document.getElementById('journal-hist-section').style.display = 'none';
    showToast('Journal généré — pensez à sauvegarder !');
  } catch(err) {
    showToast('Erreur génération : ' + err.message);
  }
  btn.disabled=false; btn.textContent='📰 Générer une édition';
}

// Sélection manuelle pour le journal
var journalManualIds = new Set();
function addToJournalSelection(btn) {
  var id = parseInt(btn.getAttribute('data-id'));
  if (journalManualIds.has(id)) {
    journalManualIds.delete(id);
    btn.classList.remove('added');
    btn.title = 'Ajouter au prochain journal';
  } else {
    journalManualIds.add(id);
    btn.classList.add('added');
    btn.title = 'Retirer du journal';
  }
  // Mettre à jour le compteur sur le bouton générer
  var count = journalManualIds.size;
  var genBtn = document.getElementById('btn-gen-journal');
  if (genBtn && count > 0) genBtn.textContent = '📰 Générer (' + count + ' sélectionnés)';
  else if (genBtn) genBtn.textContent = '📰 Générer';
}

function refreshVeille() {
  var btn = document.querySelector('#panel-veille .disp-refresh-btn');
  if (btn) { btn.classList.add('spinning'); setTimeout(function(){ btn.classList.remove('spinning'); }, 500); }
  loadArticles();
}
function refreshDispositifs() {
  var btn = document.querySelector('#panel-dispositifs .disp-refresh-btn');
  if (btn) { btn.classList.add('spinning'); setTimeout(function(){ btn.classList.remove('spinning'); }, 500); }
  loadDispositifs();
}

function loadJournalEditionById(el) { loadJournalEdition(parseInt(el.getAttribute('data-jid'))); }
function deleteJournalEditionById(e, btn) { deleteJournalEdition(e, parseInt(btn.getAttribute('data-jid'))); }
function openDispPptxById(btn) { openDispPptx(parseInt(btn.getAttribute('data-did'))); }
function openProjetById(el) { openProjet(parseInt(el.getAttribute('data-sid'))); }
function deleteProjetById(e, btn) { deleteProjet(e, parseInt(btn.getAttribute('data-sid'))); }
function collectFromShortlistById(btn) { collectFromShortlist(btn, parseInt(btn.getAttribute('data-did'))); }
function generateEmailById(btn) { generateEmail(parseInt(btn.getAttribute('data-did'))); }
function removeFromShortlistById(btn) { removeFromShortlist(parseInt(btn.getAttribute('data-did'))); }
function changeStatutById(sel) { changeStatut(sel, parseInt(sel.getAttribute('data-did'))); }

async function init() {
  buildSidebar();
  updateLockState();
  await Promise.all([loadArticles(), loadDispositifs()]);
  loadJournalHistory();
}

// ── SIDEBAR ───────────────────────────────────────────────────────────
function buildSidebar() {
  const container = document.getElementById('filter-groups');
  container.innerHTML = TAG_GROUPS.map(g => `
    <div class="filter-group" id="fg-${g.key}">
      <div class="filter-group-header" onclick="toggleGroup('${g.key}')">
        <span class="filter-group-label">${g.label}</span>
        <span class="filter-group-count" id="fc-${g.key}">0</span>
        <span class="filter-group-arrow">›</span>
      </div>
      <div class="filter-tags" id="ft-${g.key}">
        ${g.tags.map(t => `<span class="filter-tag" id="ftag-${CSS.escape(t)}" onclick="toggleTag('${g.key}','${t.replace(/'/g,"\\'")}',this)">${t}</span>`).join('')}
      </div>
    </div>
  `).join('');
  // Open first group by default
  toggleGroup('ref');
}

function toggleGroup(key) {
  document.getElementById('fg-' + key).classList.toggle('open');
}


function toggleTag(groupKey, tag, el) {
  const s = filterState[groupKey].active;
  if (s.has(tag)) { s.delete(tag); el.classList.remove('active'); }
  else { s.add(tag); el.classList.add('active'); }
  const count = s.size;
  const badge = document.getElementById('fc-' + groupKey);
  badge.textContent = count;
  badge.classList.toggle('show', count > 0);
  if (groupKey === 'ref') updateLockState();
  applyFilters();
}

function updateLockState() {
  const refActive = filterState['ref'] && filterState['ref'].active.size > 0;
  TAG_GROUPS.forEach(g => {
    if (g.key === 'ref') return;
    const el = document.getElementById('fg-' + g.key);
    if (el) el.classList.toggle('locked', !refActive);
  });
}

function clearAllFilters() {
  TAG_GROUPS.forEach(g => {
    filterState[g.key].active.clear();
    document.getElementById('fc-' + g.key).classList.remove('show');
    document.querySelectorAll(`#ft-${g.key} .filter-tag`).forEach(el => el.classList.remove('active'));
  });
  applyFilters();
}

// ── LOAD DATA ─────────────────────────────────────────────────────────
async function loadArticles() {
  try {
    const res = await fetch(API + '/api/articles?limit=2000');
    allArticles = await res.json();
    updateStats();
    applyFilters();
  } catch(e) {
    document.getElementById('articles-list').innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠️</div><div class="empty-state-title">Erreur de chargement</div></div>';
  }
}

var collectedUrls = new Set();

async function loadDispositifs() {
  try {
    var res = await fetch(API + '/api/dispositifs');
    allDispositifs = await res.json();
    // Construire le Set des URLs déjà collectées pour comparaison rapide
    collectedUrls = new Set(allDispositifs.map(function(d){ return (d.source_url||'').toLowerCase(); }));
    document.getElementById('st-dispositifs').textContent = allDispositifs.length;
    renderDispositifs(allDispositifs);
  } catch(e) {}
}

function updateStats() {
  var taggedCount = allArticles.filter(function(a){ var t=Array.isArray(a.tags)?a.tags:JSON.parse(a.tags||'[]'); return t.length>0 && !(t.length===1 && t[0]===''); }).length;
  document.getElementById('st-articles').textContent = taggedCount;
  const today = new Date().toDateString();
  const todayCount = allArticles.filter(a => new Date(a.scraped_at).toDateString() === today).length;
  document.getElementById('st-today').textContent = todayCount;
  const cdcCount = allArticles.filter(a => a.pdf_url).length;
  document.getElementById('st-cdc').textContent = cdcCount;
  renderCDC(allArticles.filter(a => a.pdf_url));
}

// ── FILTERING ─────────────────────────────────────────────────────────
// ── FILTRES VUE ──────────────────────────────────────────────────────
var viewFilter = 'all'; // all | actu | disp | cdc

function setViewFilter(mode, el) {
  viewFilter = mode;
  document.querySelectorAll('.vf-btn').forEach(function(b){ b.classList.remove('active'); });
  if (el) el.classList.add('active');
  applyFilters();
}

function setSortFromSelect(sel) {
  sortMode = sel.value;
  applyFilters();
}

function applyFilters() {
  var filtered = allArticles;

  // 1. Filtre de vue (onglets)
  if (viewFilter === 'actu') {
    filtered = filtered.filter(function(a) {
      var t = Array.isArray(a.tags) ? a.tags : JSON.parse(a.tags || '[]');
      return t.indexOf('⭐ Actualité') >= 0;
    });
  } else if (viewFilter === 'disp') {
    filtered = filtered.filter(function(a) {
      var t = Array.isArray(a.tags) ? a.tags : JSON.parse(a.tags || '[]');
      return t.indexOf('⭐ Dispositif') >= 0;
    });
  } else if (viewFilter === 'cdc') {
    filtered = filtered.filter(function(a) { return !!a.pdf_url; });
  }

  // 2. Recherche texte
  if (searchQ) {
    var q = searchQ.toLowerCase();
    filtered = filtered.filter(function(a) {
      return (a.title||'').toLowerCase().includes(q) ||
             (a.summary||'').toLowerCase().includes(q) ||
             (a.source||'').toLowerCase().includes(q);
    });
  }

  // 3. Filtres tags sidebar
  TAG_GROUPS.forEach(function(g) {
    var active = filterState[g.key].active;
    if (!active.size) return;
    filtered = filtered.filter(function(a) {
      var tags = Array.isArray(a.tags) ? a.tags : JSON.parse(a.tags || '[]');
      return [...active].some(function(t){ return tags.includes(t); });
    });
  });

  // 4. Tri
  if (sortMode === 'cdc') {
    filtered.sort(function(a, b) {
      if (a.pdf_url && !b.pdf_url) return -1;
      if (!a.pdf_url && b.pdf_url) return 1;
      return new Date(b.scraped_at) - new Date(a.scraped_at);
    });
  } else if (sortMode === 'dispositif') {
    filtered.sort(function(a, b) {
      var ad = (Array.isArray(a.tags)?a.tags:JSON.parse(a.tags||'[]')).includes('⭐ Dispositif');
      var bd = (Array.isArray(b.tags)?b.tags:JSON.parse(b.tags||'[]')).includes('⭐ Dispositif');
      if (ad && !bd) return -1; if (!ad && bd) return 1;
      return new Date(b.scraped_at) - new Date(a.scraped_at);
    });
  } else {
    filtered.sort(function(a, b) { return new Date(b.scraped_at) - new Date(a.scraped_at); });
  }

  document.getElementById('result-count').textContent = filtered.length + ' article' + (filtered.length > 1 ? 's' : '');
  renderArticles(filtered);
}

// ── RENDER ARTICLES ───────────────────────────────────────────────────
function renderArticles(list) {
  var DISP = '⭐ Dispositif', ACT = '⭐ Actualité';
  var disps = list.filter(function(a){ var t=Array.isArray(a.tags)?a.tags:JSON.parse(a.tags||'[]'); return t.indexOf(DISP)>=0; });
  var acts  = list.filter(function(a){ var t=Array.isArray(a.tags)?a.tags:JSON.parse(a.tags||'[]'); return t.indexOf(ACT)>=0; });
  var container = document.getElementById('articles-list');
  if (!disps.length && !acts.length) {
    container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠️</div><div class="empty-state-title">Aucun résultat</div><p>Sélectionnez ⭐ Dispositif ou ⭐ Actualité</p></div>';
    return;
  }
  var html = '';
  if (disps.length) {
    html += '<div class="section-label">⭐ Dispositifs <span class="section-count">'+disps.length+'</span></div>';
    html += renderCards(disps, true);
  }
  if (acts.length) {
    html += '<div class="section-label">📰 Actualités <span class="section-count">'+acts.length+'</span></div>';
    html += renderCards(acts, false);
  }
  container.innerHTML = html;
  // Attacher les events après injection
  container.querySelectorAll('.abtn-collect').forEach(function(btn){
    btn.addEventListener('click', collectFromVeille);
  });
  container.querySelectorAll('.card-title-link').forEach(function(a){
    a.addEventListener('click', function(e){ e.stopPropagation(); });
  });
}

function renderCards(list, showCollect) {
  return list.map(function(a) {
    var tags     = Array.isArray(a.tags) ? a.tags : JSON.parse(a.tags || '[]');
    var isDisp   = tags.indexOf('⭐ Dispositif') >= 0;
    var hasCDC   = !!a.pdf_url;
    var date     = a.scraped_at ? new Date(a.scraped_at).toLocaleDateString('fr-FR',{day:'numeric',month:'short'}) : '';
    var subTags  = tags.filter(function(t){ return t.charAt(0) !== '⭐'; }).slice(0, 4);

    // Construire les badges tags
    var tagsHTML = (isDisp ? '<span class="atag atag-ref">⭐ Dispositif</span>' : '<span class="atag">⭐ Actualité</span>');
    tagsHTML += subTags.map(function(t){ return '<span class="atag">'+t+'</span>'; }).join('');

    // Ligne d'actions : CDC + Collecter — PAS de lien imbriqué dans lien
    var actionsHTML = '';
    if (showCollect) {
      if (hasCDC) {
        actionsHTML += '<button class="abtn abtn-cdc" onclick="openCDC(this);event.stopPropagation();" data-url="'+encodeURI(a.pdf_url)+'">📋 CDC</button>';
      } else {
        actionsHTML += '<span class="abtn abtn-nocdc">📋 Pas de CDC</span>';
      }
      var alreadyCollected = collectedUrls.has((a.url||'').toLowerCase());
      if (alreadyCollected) {
        actionsHTML += '<span class="abtn abtn-collected">✓ Collecté</span>';
      } else {
        actionsHTML += '<button class="abtn abtn-collect'+(hasCDC?' abtn-collect-cdc':'')+'" data-url="'+encodeURIComponent(a.url||'')+'" data-title="'+encodeURIComponent(a.title||'')+'" data-id="'+(a.id||0)+'" data-pdf="'+encodeURIComponent(a.pdf_url||'')+'">💾 Collecter</button>';
      }
    } else {
      // Bouton Lire + Ajouter au Journal
      var safeArticleUrl = (a.url||'').replace(/"/g,'&quot;');
      actionsHTML += '<a class="abtn abtn-resume" href="'+safeArticleUrl+'" target="_blank" rel="noopener" onclick="event.stopPropagation()">🔗 Lire</a>';
      actionsHTML += '<button class="abtn abtn-journal" onclick="addToJournalSelection(this);event.stopPropagation();" data-id="'+(a.id||0)+'" title="Ajouter au prochain journal">📰</button>';
    }

    var card = '<div class="acard'+(isDisp?' acard-disp':'')+(hasCDC?' acard-cdc':'')+'">';
    card += '<div class="acard-header">';
    card += '<span class="acard-source">'+(a.source||'')+'</span>';
    card += '<span class="acard-date">'+date+'</span>';
    card += '</div>';
    card += '<div class="acard-title"><a class="card-title-link" href="'+encodeURI(a.url||'')+'" target="_blank">'+a.title+'</a></div>';
    if (a.summary) card += '<div class="acard-summary">'+a.summary+'</div>';
    card += '<div class="acard-footer"><div class="acard-tags">'+tagsHTML+'</div><div class="acard-actions">'+actionsHTML+'</div></div>';
    card += '</div>';
    return card;
  }).join('');
}


// ── RENDER DISPOSITIFS ────────────────────────────────────────────────
function renderDispositifs(list) {
  const container = document.getElementById('disp-grid');
  document.getElementById('disp-count').textContent = list.length + ' dispositif' + (list.length > 1 ? 's' : '');
  if (!list.length) {
    container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🗄</div><div class="empty-state-title">Aucun dispositif collecté</div></div>';
    return;
  }
  container.innerHTML = list.map(d => {
    const empty = v => !v || v === 'Information non fournie';
    return `<div class="disp-card">
      <div class="disp-card-header">
        <div class="disp-card-icon">📄</div>
        <div>
          <div class="disp-card-title">${d.titre || 'Dispositif'}</div>
          <div class="disp-card-financeur">${d.guichet_financeur || ''}</div>
        </div>
      </div>
      ${!empty(d.beneficiaire) ? `<div class="disp-field"><div class="disp-field-label">Bénéficiaires</div><div class="disp-field-val">${d.beneficiaire}</div></div>` : ''}
      ${!empty(d.territoire) ? `<div class="disp-field"><div class="disp-field-label">Territoire</div><div class="disp-field-val">${d.territoire}</div></div>` : ''}
      ${!empty(d.montants_taux) ? `<div class="disp-field"><div class="disp-field-label">Montants & taux</div><div class="disp-field-val">${d.montants_taux}</div></div>` : ''}
      ${!empty(d.date_fermeture) ? `<div class="disp-field"><div class="disp-field-label">Clôture</div><div class="disp-field-val">${d.date_fermeture}</div></div>` : ''}
      <div class="disp-card-footer">
        <button class="disp-btn primary" onclick="openDispModal(${d.id})">👁 Voir le détail</button>
        <a class="disp-btn" href="/api/dispositifs/${d.id}/export-pptx" target="_blank">📊 PPTX</a>
      </div>
    </div>`;
  }).join('');
}

// ── FILTER DISPOSITIFS ───────────────────────────────────────────────
// ── VUE DISPOSITIFS ───────────────────────────────────────────────────
var dispView = 'cards';
var dispSortCol = '';
var dispSortDir = 1;

function setDispView(mode, btn) {
  dispView = mode;
  document.querySelectorAll('.dv-btn').forEach(function(b){ b.classList.remove('active'); });
  if (btn) btn.classList.add('active');
  document.getElementById('disp-grid').style.display      = mode === 'cards' ? '' : 'none';
  document.getElementById('disp-table-wrap').style.display = mode === 'table' ? '' : 'none';
  filterDispositifs();
}

function sortDispTable(col) {
  if (dispSortCol === col) dispSortDir *= -1;
  else { dispSortCol = col; dispSortDir = 1; }
  filterDispositifs();
}

function filterDispositifs() {
  var q      = (document.getElementById('disp-search').value || '').toLowerCase();
  var benef  = document.getElementById('disp-filter-benef').value;
  var terr   = document.getElementById('disp-filter-territoire').value;
  var nature = (document.getElementById('disp-filter-nature') || {}).value || '';
  var depot  = (document.getElementById('disp-filter-depot') || {}).value || '';

  var list = allDispositifs.filter(function(d) {
    if (q && !(
      (d.titre||'').toLowerCase().includes(q) ||
      (d.guichet_financeur||'').toLowerCase().includes(q) ||
      (d.objectif||'').toLowerCase().includes(q) ||
      (d.beneficiaire||'').toLowerCase().includes(q)
    )) return false;
    if (benef  && !(d.beneficiaire||'').toLowerCase().includes(benef.toLowerCase())) return false;
    if (terr   && !(d.territoire||'').toLowerCase().includes(terr.toLowerCase())) return false;
    if (nature && !(d.nature||'').toLowerCase().includes(nature.toLowerCase())) return false;
    if (depot  && !(d.type_depot||'').toLowerCase().includes(depot.toLowerCase())) return false;
    return true;
  });

  if (dispSortCol) {
    list = list.slice().sort(function(a, b) {
      var va = (a[dispSortCol] || '').toLowerCase();
      var vb = (b[dispSortCol] || '').toLowerCase();
      return va < vb ? -dispSortDir : va > vb ? dispSortDir : 0;
    });
  } else {
    // Tri par défaut : plus récemment collecté en premier
    list = list.slice().sort(function(a, b) {
      return new Date(b.collected_at||0) - new Date(a.collected_at||0);
    });
  }

  document.getElementById('disp-count').textContent = list.length + ' dispositif' + (list.length > 1 ? 's' : '');
  renderDispositifs(list);
  if (dispView === 'table') renderDispTable(list);
}

function renderDispTable(list) {
  var tbody = document.getElementById('disp-table-body');
  if (!list.length) {
    tbody.innerHTML = '<tr><td colspan="16" style="text-align:center;padding:32px;color:var(--muted);">Aucun dispositif</td></tr>';
    return;
  }
  function cell(v) { return v && v !== 'Information non fournie' ? v : '<span class="dt-empty">—</span>'; }
  function depotBadge(v) {
    var cls = 'dt-badge ';
    if (!v || v === 'Information non fournie') return '<span class="dt-empty">—</span>';
    var vl = v.toLowerCase();
    if (vl.includes('fil') || vl.includes('continu')) cls += 'dt-badge-depot-eau';
    else if (vl.includes('clôtur') || vl.includes('clotur')) cls += 'dt-badge-depot-clos';
    else if (vl.includes('attente') || vl.includes('renouvell')) cls += 'dt-badge-depot-att';
    else cls += 'dt-badge-depot-date';
    return '<span class="' + cls + '">' + v + '</span>';
  }
  tbody.innerHTML = list.map(function(d) {
    return '<tr>' +
      '<td title="' + (d.titre||'') + '" style="font-weight:700;max-width:200px;">' + cell(d.titre) + '</td>' +
      '<td>' + cell(d.guichet_financeur) + '</td>' +
      '<td>' + cell(d.nature) + '</td>' +
      '<td>' + cell(d.beneficiaire) + '</td>' +
      '<td>' + cell(d.territoire) + '</td>' +
      '<td>' + depotBadge(d.type_depot) + '</td>' +
      '<td>' + cell(d.date_fermeture) + '</td>' +
      '<td class="wrap" style="max-width:180px;white-space:normal;">' + cell(d.montants_taux) + '</td>' +
      '<td class="wrap" style="max-width:180px;white-space:normal;">' + cell(d.objectif) + '</td>' +
      '<td class="wrap" style="max-width:180px;white-space:normal;">' + cell(d.depenses_eligibles) + '</td>' +
      '<td class="wrap" style="max-width:180px;white-space:normal;">' + cell(d.criteres_eligibilite) + '</td>' +
      '<td class="wrap" style="max-width:160px;white-space:normal;">' + cell(d.points_vigilance) + '</td>' +
      '<td>' + cell(d.guichet_instructeur) + '</td>' +
      '<td>' + cell(d.programme_europeen) + '</td>' +
      '<td>' + cell(d.contact) + '</td>' +
      '<td style="text-align:center;white-space:nowrap;">' +
        '<button class="dt-export-btn" data-did="' + (d.id||0) + '" onclick="openDispPptxById(this)">📊 PPTX</button>' +
      '</td>' +
      '</tr>';
  }).join('');
}


// ── COLLECTE MANUELLE ─────────────────────────────────────────────────
var manualCollectData = null;
var MC_FIELDS = [
  ['Titre',              'titre'],
  ['Guichet financeur',  'guichet_financeur'],
  ['Guichet instructeur','guichet_instructeur'],
  ['Nature',             'nature'],
  ['Beneficiaire',       'beneficiaire'],
  ['Type de depot',      'type_depot'],
  ['Date de fermeture',  'date_fermeture'],
  ['Objectif',           'objectif'],
  ['Types de depenses',  'types_depenses'],
  ['Operations eligibles','operations_eligibles'],
  ['Depenses eligibles', 'depenses_eligibles'],
  ['Criteres eligibilite','criteres_eligibilite'],
  ['Depenses ineligibles','depenses_ineligibles'],
  ['Montants et taux',   'montants_taux'],
  ['Thematiques',        'thematiques'],
  ['Territoire',         'territoire'],
  ['Points de vigilance','points_vigilance'],
  ['Contact',            'contact'],
  ['Programme europeen', 'programme_europeen']
];

function openManualCollect() {
  manualCollectData = null;
  mc_excel_file = null;
  mc_cdc_file = null;
  mc_cdc_data = null;
  document.getElementById('mc-url-input').value = '';
  document.getElementById('mc-cdc-status').textContent = '';
  document.getElementById('mc-result-area').innerHTML = '<div style="text-align:center;color:var(--muted);font-size:12px;padding:24px 0;">Entrez une URL puis cliquez sur Analyser.</div>';
  document.getElementById('mc-footer').style.display = 'none';
  document.getElementById('mc-run-btn').disabled = false;
  document.getElementById('mc-run-btn').textContent = 'Analyser';
  document.getElementById('mc-batch-area').innerHTML = '<div style="text-align:center;color:var(--muted);font-size:12px;padding:28px 0;">Importez un fichier Excel pour démarrer la collecte.</div>';
  document.getElementById('mc-batch-btn').disabled = true;
  document.getElementById('mc-batch-btn').textContent = 'Lancer la collecte';
  document.getElementById('mc-batch-btn').onclick = runBatchCollect;
  document.getElementById('mc-file-name').style.display = 'none';
  document.getElementById('mc-file-input').value = '';
  document.getElementById('mc-dropzone').style.borderColor = 'var(--border)';
  document.getElementById('mc-dropzone').style.background = '';
  document.getElementById('mc-pkg-check').checked = false;
  document.getElementById('mc-pkg-name-wrap').style.display = 'none';
  document.getElementById('mc-pkg-name').value = '';
  document.getElementById('mc-cdc-url-input').value = '';
  document.getElementById('mc-cdc-file-name').style.display = 'none';
  document.getElementById('mc-cdc-result-area').innerHTML = '<div style="text-align:center;color:var(--muted);font-size:12px;padding:32px 0;">Importez un CDC pour demarrer l analyse.</div>';
  document.getElementById('mc-cdc-footer').style.display = 'none';
  document.getElementById('mc-cdc-run-btn').disabled = true;
  document.getElementById('mc-cdc-run-btn').textContent = 'Analyser le CDC';
  document.getElementById('mc-cdc-dropzone').style.borderColor = 'var(--border)';
  document.getElementById('mc-cdc-dropzone').style.background = '';
  if (document.getElementById('mc-cdc-file')) document.getElementById('mc-cdc-file').value = '';
  mc_text_data = null;
  document.getElementById('mc-text-url').value = '';
  document.getElementById('mc-text-area').value = '';
  document.getElementById('mc-text-result').innerHTML = '<div style="text-align:center;color:var(--muted);font-size:12px;padding:20px 0;">Collez du texte puis cliquez sur Analyser.</div>';
  document.getElementById('mc-text-footer').style.display = 'none';
  switchMcTab('url');
  document.getElementById('manual-collect-modal').style.display = 'flex';
  setTimeout(function(){ document.getElementById('mc-url-input').focus(); }, 100);
}

function closeManualCollect() {
  document.getElementById('manual-collect-modal').style.display = 'none';
}

async function runManualCollect() {
  var url = document.getElementById('mc-url-input').value.trim();
  if (!url) { document.getElementById('mc-url-input').style.borderColor = '#c8392b'; return; }
  var btn = document.getElementById('mc-run-btn');
  btn.disabled = true;
  btn.textContent = 'Analyse en cours…';
  document.getElementById('mc-cdc-status').textContent = 'Scraping en cours…';
  document.getElementById('mc-footer').style.display = 'none';
  document.getElementById('mc-result-area').innerHTML = '<div style="display:flex;flex-direction:column;align-items:center;gap:12px;padding:32px;color:var(--muted);"><div class="spinner"></div><div style="font-size:12px;">Analyse IA en cours (15-25 s)…</div></div>';
  try {
    var res = await fetch(API + '/api/collect', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url: url, title: ''})
    });
    var data = await res.json();
    if (data.error) throw new Error(data.error);
    manualCollectData = data;
    manualCollectData.source_url = url;
    if (data.cdc_url) {
      var fname = data.cdc_url.split('/').slice(-1)[0].substring(0, 50);
      document.getElementById('mc-cdc-status').innerHTML = 'CDC detecte et analyse en priorite : <a href="' + data.cdc_url + '" target="_blank" style="color:var(--accent);">' + fname + '</a>';
    } else {
      document.getElementById('mc-cdc-status').textContent = 'Pas de CDC detecte — analyse basee sur la page web';
    }
    var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;">';
    MC_FIELDS.forEach(function(f) {
      var val = data[f[1]];
      var empty = !val || val === 'Information non fournie';
      var disp = empty ? '<em style="color:var(--muted2);">Non renseigne</em>' : val;
      html += '<div style="background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px;' + (empty ? 'opacity:0.55;' : '') + '">';
      html += '<div style="font-size:9.5px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">' + f[0] + '</div>';
      html += '<div style="font-size:12px;line-height:1.4;">' + disp + '</div></div>';
    });
    html += '</div>';
    document.getElementById('mc-result-area').innerHTML = html;
    document.getElementById('mc-footer').style.display = 'flex';
  } catch(e) {
    document.getElementById('mc-cdc-status').textContent = '';
    document.getElementById('mc-result-area').innerHTML = '<div style="background:rgba(200,57,43,0.07);border:1px solid rgba(200,57,43,0.2);border-radius:6px;padding:14px;color:#a0291e;font-size:12px;">Erreur : ' + e.message + '</div>';
  }
  btn.disabled = false;
  btn.textContent = 'Analyser';
}

async function saveManualCollect() {
  if (!manualCollectData) return;
  var btn = document.getElementById('mc-save-btn');
  btn.disabled = true;
  btn.textContent = 'Sauvegarde…';
  try {
    var res = await fetch(API + '/api/dispositifs', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(manualCollectData)
    });
    var saved = await res.json();
    if (saved.status === 'duplicate') {
      showToast('Dispositif deja dans la base !');
    } else {
      showToast('Dispositif ajoute a la base !');
      closeManualCollect();
      loadDispositifs();
    }
  } catch(e) {
    showToast('Erreur sauvegarde : ' + e.message);
  }
  btn.disabled = false;
  btn.textContent = 'Sauvegarder';
}

// ── TEXT / SCRAPE MANUEL ─────────────────────────────────────────────
var mc_text_data = null;

async function runTextCollect() {
  var text = document.getElementById('mc-text-area').value.trim();
  if (!text) { showToast('Collez du contenu a analyser'); return; }
  var btn = document.getElementById('mc-text-run-btn');
  btn.disabled = true; btn.textContent = 'Analyse en cours…';
  document.getElementById('mc-text-result').innerHTML = '<div style="display:flex;flex-direction:column;align-items:center;gap:12px;padding:32px;color:var(--muted);"><div class="spinner"></div><div style="font-size:12px;">Analyse IA… (15-25 s)</div></div>';
  var sourceUrl = document.getElementById('mc-text-url').value.trim();
  try {
    var res = await fetch(API + '/api/collect-text', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ text: text, source_url: sourceUrl })
    });
    var data = await res.json();
    if (data.error) throw new Error(data.error);
    mc_text_data = data;
    var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;">';
    MC_FIELDS.forEach(function(f) {
      var val = data[f[1]];
      var empty = !val || val === 'Information non fournie';
      var disp = empty ? '<em style="color:var(--muted2);">Non renseigne</em>' : val;
      html += '<div style="background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px;' + (empty ? 'opacity:0.55;' : '') + '">';
      html += '<div style="font-size:9.5px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">' + f[0] + '</div>';
      html += '<div style="font-size:12px;line-height:1.4;">' + disp + '</div></div>';
    });
    html += '</div>';
    document.getElementById('mc-text-result').innerHTML = html;
    document.getElementById('mc-text-footer').style.display = 'flex';
  } catch(e) {
    document.getElementById('mc-text-result').innerHTML = '<div style="padding:14px;background:rgba(200,57,43,0.07);border:1px solid rgba(200,57,43,0.2);border-radius:8px;color:#a0291e;font-size:12px;">Erreur : ' + e.message + '</div>';
  }
  btn.disabled = false; btn.textContent = 'Analyser';
}

async function saveTextCollect() {
  if (!mc_text_data) return;
  var btn = document.getElementById('mc-text-save-btn');
  btn.disabled = true; btn.textContent = 'Sauvegarde…';
  try {
    var res = await fetch(API + '/api/dispositifs', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(mc_text_data)
    });
    var saved = await res.json();
    showToast(saved.status === 'duplicate' ? 'Deja dans la base !' : 'Dispositif ajoute !');
    if (saved.status !== 'duplicate') { closeManualCollect(); loadDispositifs(); }
  } catch(e) { showToast('Erreur : ' + e.message); }
  btn.disabled = false; btn.textContent = 'Sauvegarder';
}

// ── MODAL TABS ────────────────────────────────────────────────────────
function switchMcTab(tab) {
  var tabs = ['url', 'cdc', 'excel', 'text'];
  tabs.forEach(function(t) {
    var pane = document.getElementById('mc-pane-' + t);
    var btn  = document.getElementById('mc-tab-' + t);
    if (!pane || !btn) return;
    var active = t === tab;
    pane.style.display = active ? 'flex' : 'none';
    btn.style.background = active ? 'var(--surface)' : 'transparent';
    btn.style.color = active ? 'var(--accent)' : 'var(--muted)';
    btn.style.borderBottomColor = active ? 'var(--accent)' : 'transparent';
  });
}

// ── CDC TAB ───────────────────────────────────────────────────────────
var mc_cdc_file = null;
var mc_cdc_data = null;

function onCdcFileSelected(input) {
  var f = input.files[0];
  if (!f) return;
  mc_cdc_file = f;
  var fn = document.getElementById('mc-cdc-file-name');
  fn.textContent = f.name;
  fn.style.display = 'block';
  document.getElementById('mc-cdc-run-btn').disabled = false;
  document.getElementById('mc-cdc-dropzone').style.borderColor = 'var(--accent)';
  document.getElementById('mc-cdc-dropzone').style.background = 'var(--lime-bg)';
}

async function runCdcCollect() {
  if (!mc_cdc_file) { showToast('Importez un fichier CDC'); return; }
  var btn = document.getElementById('mc-cdc-run-btn');
  btn.disabled = true;
  btn.textContent = 'Analyse en cours…';
  document.getElementById('mc-cdc-result-area').innerHTML = '<div style="display:flex;flex-direction:column;align-items:center;gap:12px;padding:32px;color:var(--muted);"><div class="spinner"></div><div style="font-size:12px;">Analyse IA du CDC… (15-25 s)</div></div>';

  var fd = new FormData();
  fd.append('file', mc_cdc_file);
  var sourceUrl = document.getElementById('mc-cdc-url-input').value.trim();
  if (sourceUrl) fd.append('source_url', sourceUrl);

  try {
    var res = await fetch(API + '/api/collect-cdc', { method: 'POST', body: fd });
    var data = await res.json();
    if (data.error) throw new Error(data.error);
    mc_cdc_data = data;

    var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;">';
    MC_FIELDS.forEach(function(f) {
      var val = data[f[1]];
      var empty = !val || val === 'Information non fournie';
      var disp = empty ? '<em style="color:var(--muted2);">Non renseigne</em>' : val;
      html += '<div style="background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px;' + (empty ? 'opacity:0.55;' : '') + '">';
      html += '<div style="font-size:9.5px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">' + f[0] + '</div>';
      html += '<div style="font-size:12px;line-height:1.4;">' + disp + '</div></div>';
    });
    html += '</div>';
    document.getElementById('mc-cdc-result-area').innerHTML = html;
    document.getElementById('mc-cdc-footer').style.display = 'flex';
  } catch(e) {
    document.getElementById('mc-cdc-result-area').innerHTML = '<div style="padding:14px;background:rgba(200,57,43,0.07);border:1px solid rgba(200,57,43,0.2);border-radius:8px;color:#a0291e;font-size:12px;">Erreur : ' + e.message + '</div>';
  }
  btn.disabled = false;
  btn.textContent = 'Analyser le CDC';
}

async function saveCdcCollect() {
  if (!mc_cdc_data) return;
  var btn = document.getElementById('mc-cdc-save-btn');
  btn.disabled = true;
  btn.textContent = 'Sauvegarde…';
  try {
    var res = await fetch(API + '/api/dispositifs', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(mc_cdc_data)
    });
    var saved = await res.json();
    if (saved.status === 'duplicate') {
      showToast('Dispositif deja dans la base !');
    } else {
      showToast('Dispositif ajoute !');
      closeManualCollect();
      loadDispositifs();
    }
  } catch(e) {
    showToast('Erreur : ' + e.message);
  }
  btn.disabled = false;
  btn.textContent = 'Sauvegarder';
}

// ── EXCEL UPLOAD ──────────────────────────────────────────────────────
var mc_excel_file = null;

function onExcelFileSelected(input) {
  var f = input.files[0];
  if (!f) return;
  mc_excel_file = f;
  var fn = document.getElementById('mc-file-name');
  fn.textContent = f.name + ' — prêt';
  fn.style.display = 'block';
  document.getElementById('mc-batch-btn').disabled = false;
  document.getElementById('mc-dropzone').style.borderColor = 'var(--accent)';
  document.getElementById('mc-dropzone').style.background = 'var(--lime-bg)';
  document.getElementById('mc-batch-area').innerHTML = '<div style="text-align:center;color:var(--accent);font-size:12px;padding:24px 0;font-weight:600;">Fichier chargé — cliquez sur Lancer la collecte.</div>';
}

function togglePkgName() {
  var checked = document.getElementById('mc-pkg-check').checked;
  document.getElementById('mc-pkg-name-wrap').style.display = checked ? 'block' : 'none';
  if (checked) setTimeout(function(){ document.getElementById('mc-pkg-name').focus(); }, 80);
}

var batchPollTimer = null;

async function runBatchCollect() {
  if (!mc_excel_file) { showToast('Importez un fichier Excel'); return; }
  var btn = document.getElementById('mc-batch-btn');
  var createPkg = document.getElementById('mc-pkg-check').checked;
  var pkgName = createPkg ? document.getElementById('mc-pkg-name').value.trim() : '';
  if (createPkg && !pkgName) { document.getElementById('mc-pkg-name').focus(); showToast('Donnez un nom au package'); return; }

  btn.disabled = true;
  btn.textContent = 'Lancement…';
  var area = document.getElementById('mc-batch-area');
  area.innerHTML = '<div style="display:flex;align-items:center;gap:10px;padding:16px;background:var(--surface2);border-radius:8px;"><div class="spinner"></div><span style="font-size:12px;color:var(--muted);">Envoi du fichier…</span></div>';

  var fd = new FormData();
  fd.append('file', mc_excel_file);
  if (createPkg) { fd.append('create_package', 'true'); fd.append('package_name', pkgName); }

  try {
    var res = await fetch(API + '/api/collect-batch', { method: 'POST', body: fd });
    var data = await res.json();
    if (data.error) throw new Error(data.error);

    var jobId = data.job_id;
    var total = data.total;
    btn.textContent = 'En cours…';

    // Start polling
    batchPollTimer = setInterval(async function() {
      try {
        var pr = await fetch(API + '/api/collect-batch/' + jobId);
        var job = await pr.json();
        var done = job.done || 0;
        var results = job.results || [];

        // Progress bar
        var pct = total > 0 ? Math.round(done / total * 100) : 0;
        var lastResult = results.length ? results[results.length - 1] : null;
        var lastTitle = lastResult ? (lastResult.titre || lastResult.url).substring(0, 55) : '';
        var statusIcon = lastResult ? (lastResult.status === 'saved' ? '✅' : lastResult.status === 'duplicate' ? '⚠️' : '❌') : '';

        var progressHtml = '<div style="margin-bottom:12px;">';
        progressHtml += '<div style="display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin-bottom:6px;">';
        progressHtml += '<span>' + done + ' / ' + total + ' analysés</span><span>' + pct + '%</span></div>';
        progressHtml += '<div style="background:var(--border);border-radius:100px;height:6px;">';
        progressHtml += '<div style="background:var(--accent);height:6px;border-radius:100px;width:' + pct + '%;transition:width 0.3s;"></div></div>';
        if (lastTitle) progressHtml += '<div style="margin-top:8px;font-size:11px;color:var(--muted);">' + statusIcon + ' ' + lastTitle + '</div>';
        progressHtml += '</div>';

        // Results list (last 5)
        if (results.length) {
          progressHtml += '<div style="display:flex;flex-direction:column;gap:4px;max-height:200px;overflow-y:auto;">';
          results.slice().reverse().slice(0, 8).forEach(function(r) {
            var icon = r.status === 'saved' ? '✅' : r.status === 'duplicate' ? '⚠️' : '❌';
            var label = (r.titre || r.url).substring(0, 60);
            var sub = r.status === 'saved' ? 'Ajouté' : r.status === 'duplicate' ? 'Doublon' : (r.error || 'Erreur').substring(0, 50);
            progressHtml += '<div style="display:flex;gap:8px;padding:6px 8px;background:var(--surface2);border-radius:5px;font-size:10.5px;">';
            progressHtml += '<span style="flex-shrink:0;">' + icon + '</span>';
            progressHtml += '<div style="flex:1;overflow:hidden;"><div style="font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + label + '</div>';
            progressHtml += '<div style="color:var(--muted);">' + sub + '</div></div></div>';
          });
          progressHtml += '</div>';
        }

        area.innerHTML = progressHtml;

        if (job.status === 'done') {
          clearInterval(batchPollTimer);
          var saved = results.filter(function(r){ return r.status === 'saved'; }).length;
          var dupes = results.filter(function(r){ return r.status === 'duplicate'; }).length;
          var errorList = results.filter(function(r){ return r.status === 'error'; });
          var errors = errorList.length;

          var summary = '<div style="padding:10px 14px;background:rgba(30,143,84,0.08);border-radius:8px;border:1px solid rgba(30,143,84,0.2);margin-bottom:8px;">';
          summary += '<span style="font-size:12px;font-weight:700;color:#1a7a3e;">Terminé — ' + saved + ' sauvegardé(s)</span>';
          if (dupes) summary += ' · <span style="font-size:11px;color:var(--muted);">' + dupes + ' doublon(s)</span>';
          if (errors) summary += ' · <span style="font-size:11px;color:#c8392b;">' + errors + ' erreur(s)</span>';
          summary += '</div>';

          if (errors) {
            summary += '<div style="margin-bottom:8px;">';
            summary += '<div style="font-size:10.5px;font-weight:700;color:#c8392b;text-transform:uppercase;letter-spacing:.07em;margin-bottom:6px;">Sources non collectées</div>';
            errorList.forEach(function(r) {
              var msg = (r.error || 'Erreur inconnue').substring(0, 80);
              var shortUrl = r.url.replace(/^https?:\/\//, '').substring(0, 55);
              summary += '<div style="display:flex;gap:8px;align-items:flex-start;padding:7px 10px;background:rgba(200,57,43,0.05);border:1px solid rgba(200,57,43,0.15);border-radius:6px;margin-bottom:4px;">';
              summary += '<span style="flex-shrink:0;font-size:13px;">❌</span>';
              summary += '<div style="flex:1;min-width:0;">';
              summary += '<div style="font-size:11px;font-weight:600;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="' + r.url + '">' + shortUrl + '</div>';
              summary += '<div style="font-size:10px;color:#c8392b;margin-top:2px;">' + msg + '</div>';
              summary += '</div>';
              summary += '<a href="' + r.url + '" target="_blank" style="flex-shrink:0;font-size:10px;color:var(--accent);opacity:0.7;margin-top:1px;">↗</a>';
              summary += '</div>';
            });
            summary += '</div>';
          }

          if (job.pkg_id) {
            summary += '<div style="padding:9px 14px;background:var(--lime-bg);border-radius:8px;border:1px solid rgba(200,232,78,0.35);font-size:11px;color:var(--accent);font-weight:600;margin-bottom:8px;">&#x1F4E6; Package &laquo;' + (job.pkg_name || '') + '&raquo; : ' + saved + ' dispositif(s)</div>';
            loadPackages();
          }
          area.innerHTML = summary + area.innerHTML;
          loadDispositifs();
          btn.textContent = 'Fermer';
          btn.disabled = false;
          btn.onclick = closeManualCollect;
        }
      } catch(e) { /* polling error, continue */ }
    }, 3000);  // Poll every 3 seconds

  } catch(e) {
    area.innerHTML = '<div style="padding:14px;background:rgba(200,57,43,0.07);border:1px solid rgba(200,57,43,0.2);border-radius:8px;color:#a0291e;font-size:12px;">Erreur : ' + e.message + '</div>';
    btn.disabled = false;
    btn.textContent = 'Réessayer';
  }
}

// ── PACKAGES ──────────────────────────────────────────────────────────
var currentPkgId = null;

async function loadPackages() {
  var list = document.getElementById('pkg-list');
  try {
    var res = await fetch(API + '/api/packages');
    var pkgs = await res.json();
    document.getElementById('pkg-list-count').textContent = pkgs.length + ' package' + (pkgs.length > 1 ? 's' : '');
    if (!pkgs.length) {
      list.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:48px 24px;color:var(--muted);">' +
        '<div style="font-size:32px;margin-bottom:10px;">&#x1F4E6;</div>' +
        '<div style="font-size:13px;font-weight:700;margin-bottom:6px;">Aucun package</div>' +
        '<div style="font-size:12px;">Importez un fichier Excel et cochez Regrouper dans un Package</div></div>';
      return;
    }
    var html = '';
    pkgs.forEach(function(p) {
      var d = p.created_at ? new Date(p.created_at).toLocaleDateString('fr-FR') : '';
      html += '<div data-pkgid="' + p.id + '" data-pkgname="' + p.name.replace(/"/g,'&quot;') + '" class="pkg-card">';
      html += '<div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px;">';
      html += '<div style="width:38px;height:38px;background:var(--lime-bg);border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:20px;">&#x1F4E6;</div>';
      html += '<button class="pkg-del-btn" data-pid="' + p.id + '" style="background:none;border:none;cursor:pointer;color:var(--muted);font-size:13px;padding:4px 6px;border-radius:5px;">&#x2715;</button>';
      html += '</div>';
      html += '<div style="font-weight:800;font-size:14px;color:var(--accent);margin-bottom:5px;">' + p.name + '</div>';
      html += '<div style="font-size:11px;color:var(--muted);">' + p.nb + ' dispositif' + (p.nb > 1 ? 's' : '') + ' &middot; ' + d + '</div>';
      html += '</div>';
    });
    list.innerHTML = html;
    list.querySelectorAll('.pkg-card').forEach(function(card) {
      card.style.cssText = 'background:var(--surface);border:1.5px solid var(--border);border-radius:12px;padding:18px 20px;cursor:pointer;transition:all 0.18s;';
      card.addEventListener('mouseenter', function(){ this.style.borderColor='var(--accent)'; this.style.transform='translateY(-2px)'; });
      card.addEventListener('mouseleave', function(){ this.style.borderColor='var(--border)'; this.style.transform=''; });
      card.addEventListener('click', function(e) {
        if (e.target.classList.contains('pkg-del-btn')) return;
        openPkgDetail(parseInt(this.dataset.pkgid), this.dataset.pkgname);
      });
    });
    list.querySelectorAll('.pkg-del-btn').forEach(function(btn) {
      btn.addEventListener('mouseenter', function(){ this.style.color='#c8392b'; });
      btn.addEventListener('mouseleave', function(){ this.style.color='var(--muted)'; });
      btn.addEventListener('click', function(e) {
        e.stopPropagation();
        deletePackage(parseInt(this.dataset.pid), this);
      });
    });
  } catch(e) {
    list.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:32px;color:#c8392b;font-size:12px;">Erreur chargement</div>';
  }
}

function switchPkgTab(tab) {
  var tabs = ['disp', 'logs'];
  tabs.forEach(function(t) {
    var pane = document.getElementById('pkg-pane-' + t);
    var btn = document.getElementById('pkg-tab-' + t);
    if (!pane || !btn) return;
    var active = t === tab;
    pane.style.display = active ? (t === 'disp' ? 'grid' : 'block') : 'none';
    btn.style.background = active ? 'var(--surface)' : 'transparent';
    btn.style.color = active ? 'var(--accent)' : 'var(--muted)';
    btn.style.borderBottomColor = active ? 'var(--accent)' : 'transparent';
  });
  if (tab === 'logs') loadPkgLogs();
}

async function loadPkgLogs() {
  var pane = document.getElementById('pkg-pane-logs');
  pane.innerHTML = '<div style="color:var(--muted);font-size:12px;padding:24px;text-align:center;">Chargement…</div>';
  try {
    var res = await fetch(API + '/api/packages/' + currentPkgId + '/logs');
    var jobs = await res.json();
    var allErrors = [];
    jobs.forEach(function(j) {
      (j.errors || []).forEach(function(e) {
        allErrors.push({ job_id: j.job_id, date: j.created_at, url: e.url, error: e.error || 'Erreur inconnue' });
      });
    });
    var badge = document.getElementById('pkg-logs-badge');
    if (allErrors.length) {
      badge.textContent = allErrors.length;
      badge.style.display = 'inline';
    } else {
      badge.style.display = 'none';
    }
    if (!allErrors.length) {
      pane.innerHTML = '<div style="text-align:center;padding:40px;color:var(--muted);"><div style="font-size:28px;margin-bottom:8px;">✅</div><div style="font-size:12px;font-weight:600;">Aucune erreur sur ce package</div></div>';
      return;
    }
    var html = '<div style="font-size:10.5px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;">' + allErrors.length + ' source(s) non collectée(s)</div>';
    allErrors.forEach(function(e) {
      var d = e.date ? new Date(e.date).toLocaleDateString('fr-FR') : '';
      var shortUrl = (e.url || '').replace(/^https?:\/\//, '').substring(0, 60);
      html += '<div style="display:flex;gap:10px;align-items:flex-start;padding:10px 12px;background:rgba(200,57,43,0.04);border:1px solid rgba(200,57,43,0.15);border-radius:8px;margin-bottom:6px;">';
      html += '<span style="font-size:16px;flex-shrink:0;">❌</span>';
      html += '<div style="flex:1;min-width:0;">';
      html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:3px;">';
      html += '<span style="font-size:11px;font-weight:700;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;" title="' + (e.url||'') + '">' + shortUrl + '</span>';
      if (e.url) html += '<a href="' + e.url + '" target="_blank" style="font-size:10px;color:var(--accent);flex-shrink:0;">↗ Ouvrir</a>';
      html += '</div>';
      html += '<div style="font-size:10.5px;color:#c8392b;">' + e.error.substring(0, 100) + '</div>';
      if (d) html += '<div style="font-size:10px;color:var(--muted);margin-top:2px;">Collecte du ' + d + '</div>';
      html += '</div></div>';
    });
    pane.innerHTML = html;
  } catch(err) {
    pane.innerHTML = '<div style="color:#c8392b;font-size:12px;padding:16px;">Erreur chargement logs</div>';
  }
}

async function openPkgDetail(id, name) {
  currentPkgId = id;
  document.getElementById('pkg-list').style.display = 'none';
  var detail = document.getElementById('pkg-detail');
  detail.style.display = 'flex';
  document.getElementById('pkg-detail-name').textContent = name;
  document.getElementById('pkg-detail-count').textContent = '';
  switchPkgTab('disp');
  document.getElementById('pkg-logs-badge').style.display = 'none';
  document.getElementById('pkg-pane-disp').innerHTML = '<div class="spinner" style="margin:32px auto;display:block;"></div>';
  try {
    var res = await fetch(API + '/api/packages/' + id + '/dispositifs');
    var disps = await res.json();
    document.getElementById('pkg-detail-count').textContent = disps.length + ' dispositif' + (disps.length > 1 ? 's' : '');
    if (!disps.length) {
      document.getElementById('pkg-pane-disp').innerHTML = '<div style="text-align:center;color:var(--muted);font-size:12px;padding:32px;">Aucun dispositif dans ce package</div>';
      return;
    }
    var html = '';
    disps.forEach(function(d) {
      html += '<div style="background:var(--surface);border:1.5px solid var(--border);border-radius:10px;padding:14px 16px;">';
      html += '<div style="font-weight:800;font-size:12px;color:var(--accent);margin-bottom:6px;line-height:1.3;">' + (d.titre || 'Sans titre') + '</div>';
      html += '<div style="font-size:10.5px;color:var(--muted);margin-bottom:4px;">' + (d.guichet_financeur || '') + '</div>';
      html += '<div style="display:flex;gap:5px;flex-wrap:wrap;margin-top:8px;">';
      if (d.nature) html += '<span style="background:var(--lime-bg);color:#3a5a1e;font-size:9.5px;font-weight:700;padding:2px 7px;border-radius:100px;">' + d.nature + '</span>';
      if (d.territoire) html += '<span style="background:var(--surface2);color:var(--muted);font-size:9.5px;font-weight:600;padding:2px 7px;border-radius:100px;">' + d.territoire + '</span>';
      html += '</div>';
      if (d.source_url) html += '<a href="' + d.source_url + '" target="_blank" style="display:block;margin-top:8px;font-size:10px;color:var(--accent);opacity:0.6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + d.source_url + '</a>';
      html += '</div>';
    });
    document.getElementById('pkg-pane-disp').innerHTML = html;
    // Load logs badge in background
    fetch(API + '/api/packages/' + id + '/logs').then(function(r){ return r.json(); }).then(function(jobs) {
      var total = jobs.reduce(function(acc, j){ return acc + (j.errors||[]).length; }, 0);
      var badge = document.getElementById('pkg-logs-badge');
      if (total) { badge.textContent = total; badge.style.display = 'inline'; }
    }).catch(function(){});
  } catch(e) {
    document.getElementById('pkg-pane-disp').innerHTML = '<div style="color:#c8392b;font-size:12px;">Erreur</div>';
  }
}

function closePkgDetail() {
  document.getElementById('pkg-detail').style.display = 'none';
  document.getElementById('pkg-list').style.display = 'grid';
  currentPkgId = null;
}

// ── DELETE CURRENT PACKAGE ────────────────────────────────────────────
async function deleteCurrentPackage() {
  if (!currentPkgId) return;
  var name = document.getElementById('pkg-detail-name').textContent;
  if (!confirm('Supprimer le package "' + name + '" ? Les dispositifs seront détachés mais resteront dans la base.')) return;
  try {
    await fetch(API + '/api/packages/' + currentPkgId, { method: 'DELETE' });
    showToast('Package supprimé');
    closePkgDetail();
    loadPackages();
  } catch(e) { showToast('Erreur : ' + e.message); }
}

// ── MERGE MODAL ────────────────────────────────────────────────────────
async function openMergeModal() {
  if (!currentPkgId) return;
  var currentName = document.getElementById('pkg-detail-name').textContent;
  // Load other packages for select
  try {
    var res = await fetch(API + '/api/packages');
    var pkgs = await res.json();
    var others = pkgs.filter(function(p) { return p.id !== currentPkgId; });
    var sel = document.getElementById('merge-target-select');
    if (!others.length) { showToast('Aucun autre package disponible'); return; }
    sel.innerHTML = others.map(function(p) {
      return '<option value="' + p.id + '">' + p.name + ' (' + p.nb + ' dispositifs)</option>';
    }).join('');
    document.getElementById('merge-name-input').value = currentName + ' (fusionné)';
    document.getElementById('merge-modal').style.display = 'flex';
    setTimeout(function(){ document.getElementById('merge-name-input').select(); }, 100);
  } catch(e) { showToast('Erreur : ' + e.message); }
}

function closeMergeModal() {
  document.getElementById('merge-modal').style.display = 'none';
}

async function confirmMerge() {
  var targetId = parseInt(document.getElementById('merge-target-select').value);
  var newName = document.getElementById('merge-name-input').value.trim();
  if (!newName) { document.getElementById('merge-name-input').focus(); return; }
  var btn = document.getElementById('merge-confirm-btn');
  btn.disabled = true; btn.textContent = 'Fusion…';
  try {
    var res = await fetch(API + '/api/packages/merge', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ pkg_a: currentPkgId, pkg_b: targetId, name: newName })
    });
    var data = await res.json();
    if (data.error) throw new Error(data.error);
    showToast('Packages fusionnés en "' + data.name + '"');
    closeMergeModal();
    closePkgDetail();
    loadPackages();
    // Open the new merged package
    setTimeout(function(){ openPkgDetail(data.new_id, data.name); }, 400);
  } catch(e) {
    showToast('Erreur : ' + e.message);
    btn.disabled = false; btn.textContent = 'Fusionner';
  }
}

function exportPackagePptx() {
  if (!currentPkgId) return;
  window.open(API + '/api/packages/' + currentPkgId + '/export-pptx', '_blank');
}

async function exportPackageCdc() {
  if (!currentPkgId) return;
  var btn = document.getElementById('pkg-cdc-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Telechargement…'; }
  try {
    var res = await fetch(API + '/api/packages/' + currentPkgId + '/export-cdc');
    if (!res.ok) {
      var err = await res.json();
      showToast(err.error || 'Aucun CDC disponible');
      if (btn) { btn.disabled = false; btn.textContent = '📎 CDCs'; }
      return;
    }
    var blob = await res.blob();
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'CDCs_package.zip';
    a.click();
    URL.revokeObjectURL(url);
  } catch(e) {
    showToast('Erreur : ' + e.message);
  }
  if (btn) { btn.disabled = false; btn.textContent = '📎 CDCs'; }
}

async function deletePackage(id, btn) {
  if (!confirm('Supprimer ce package ? Les dispositifs restent dans la base.')) return;
  btn.disabled = true;
  try {
    await fetch(API + '/api/packages/' + id, { method: 'DELETE' });
    loadPackages();
  } catch(e) { showToast('Erreur'); }
}

// ── COLLECT ALL MISSING ───────────────────────────────────────────────
function toggleCollectMenu() {
  const menu = document.getElementById('collect-submenu');
  if (!menu) return;
  const isOpen = menu.style.display !== 'none';
  menu.style.display = isOpen ? 'none' : 'block';
  if (!isOpen) {
    setTimeout(() => {
      document.addEventListener('click', function closeMenu(e) {
        if (!document.getElementById('collect-all-wrap')?.contains(e.target)) {
          menu.style.display = 'none';
          document.removeEventListener('click', closeMenu);
        }
      });
    }, 10);
  }
}

async function collectAllMissing(mode) {
  // mode: 'all' | 'cdc' | 'nocdc'
  const menuEl = document.getElementById('collect-submenu');
  if (menuEl) menuEl.style.display = 'none';
  const btn = document.getElementById('btn-collect-all');
  const resetBtn = () => { btn.disabled = false; btn.innerHTML = '📥 Collecter tous les dispositifs <span style="font-size:9px;opacity:.8">▾</span>'; };
  btn.disabled = true;
  btn.innerHTML = '⏳ Chargement…';
  try {
    const arts = await fetch(API + '/api/articles?limit=2000').then(r => r.json());
    const collected = new Set(allDispositifs.map(d => d.source_url).filter(Boolean));
    let toCollect = arts.filter(a => {
      const tags = Array.isArray(a.tags) ? a.tags : JSON.parse(a.tags || '[]');
      return tags.includes('⭐ Dispositif') && !collected.has(a.url);
    });
    if (mode === 'cdc')   toCollect = toCollect.filter(a => !!a.pdf_url);
    if (mode === 'nocdc') toCollect = toCollect.filter(a => !a.pdf_url);

    const modeLabel = mode === 'cdc' ? 'avec CDC' : mode === 'nocdc' ? 'sans CDC' : '';
    if (!toCollect.length) {
      showToast('✅ Aucun dispositif ' + modeLabel + ' à collecter !');
      resetBtn(); return;
    }
    if (!confirm('Collecter ' + toCollect.length + ' dispositif(s) ' + (modeLabel ? '(' + modeLabel + ')' : '') + ' ? Cela utilisera des crédits Claude.')) {
      resetBtn(); return;
    }
    let done = 0, errors = 0;
    for (const a of toCollect) {
      btn.innerHTML = '⏳ ' + (done + errors + 1) + '/' + toCollect.length + '…';
      try {
        const ctrl = new AbortController();
        const tid = setTimeout(() => ctrl.abort(), 28000);
        const d = await fetch(API + '/api/collect', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({url: a.url, title: a.title, id: a.id, pdf_url: a.pdf_url || ''}),
          signal: ctrl.signal
        }).then(r => { clearTimeout(tid); return r.json(); });
        if (!d.error) {
          await fetch(API + '/api/dispositifs', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(d)
          });
          done++;
        } else { errors++; }
      } catch(e) { errors++; }
    }
    showToast('✅ ' + done + ' collecté(s)' + (errors ? ' — ' + errors + ' erreur(s)' : ''));
    loadDispositifs();
  } catch(e) {
    showToast('❌ Erreur : ' + e.message);
  }
  resetBtn();
}


function renderCDC(list) {
  const container = document.getElementById('cdc-list');
  document.getElementById('cdc-count').textContent = list.length + ' document' + (list.length > 1 ? 's' : '');
  if (!list.length) {
    container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📋</div><div class="empty-state-title">Aucun cahier des charges trouvé</div><p>Lancez une analyse CDC depuis l espace de veille</p></div>';
    return;
  }
  container.innerHTML = list.map(a => {
    const ext = (a.pdf_url||'').split('.').pop().toUpperCase().slice(0,4);
    const date = a.scraped_at ? new Date(a.scraped_at).toLocaleDateString('fr-FR') : '';
    return `<div class="cdc-card">
      <div class="cdc-icon">📄</div>
      <div class="cdc-info">
        <div class="cdc-title">${a.title}</div>
        <div class="cdc-meta">${a.source || ''} · ${date} · ${ext || 'DOC'}</div>
      </div>
      <div class="cdc-actions">
        <a class="cdc-btn" href="${a.url}" target="_blank" rel="noopener">🔗 Fiche</a>
        <a class="cdc-btn dl" href="${a.pdf_url}" target="_blank" rel="noopener" download>⬇ Télécharger</a>
      </div>
    </div>`;
  }).join('');
}

// ── MODAL DISPOSITIF ──────────────────────────────────────────────────
function openDispModal(id) {
  const d = allDispositifs.find(x => x.id === id);
  if (!d) return;
  currentDispId = id;
  document.getElementById('modal-title').textContent = '📄 ' + (d.titre || 'Dispositif');
  const fields = [
    ["Guichet financeur", d.guichet_financeur],
    ["Guichet instructeur", d.guichet_instructeur],
    ["Nature", d.nature],
    ["Bénéficiaires", d.beneficiaire],
    ["Type de dépôt", d.type_depot],
    ["Date de clôture", d.date_fermeture],
    ["Montants & taux", d.montants_taux],
    ["Territoire", d.territoire],
    ["Thématiques", d.thematiques],
    ["Objectif", d.objectif, true],
    ["Dépenses éligibles", d.depenses_eligibles, true],
    ["Critères d’éligibilité", d.criteres_eligibilite, true],
    ["Points de vigilance", d.points_vigilance, true],
    ["Contact", d.contact],
  ];
  const empty = v => !v || v === 'Information non fournie';
  document.getElementById('modal-body').innerHTML = fields.map(([label, val, full]) => {
    const isEmpty = empty(val);
    return `<div class="modal-field${full ? ' full' : ''}">
      <div class="modal-field-label">${label}</div>
      <div class="modal-field-val${isEmpty ? ' empty' : ''}">${isEmpty ? 'Non renseigné' : val}</div>
    </div>`;
  }).join('');
  document.getElementById('modal').classList.add('open');
}
function closeModal() { document.getElementById('modal').classList.remove('open'); }
function openDispPptx(id) {
  window.open(API + '/api/dispositifs/' + id + '/export-pptx', '_blank');
}

function exportDispPptx() {
  if (currentDispId) window.open(API + '/api/dispositifs/' + currentDispId + '/export-pptx', '_blank');
}

// ── NAV ───────────────────────────────────────────────────────────────
function switchTab(tab, btn) {
  activeTab = tab;
  document.querySelectorAll('.header-tab').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  var panel = document.getElementById('panel-' + tab);
  if (panel) panel.classList.add('active');
  if (tab === 'veille360') loadV360Sessions();
  if (tab === 'dispositifs') loadDispositifs();
  if (tab === 'packages') loadPackages();
}

// ── ESPACE PROJET ────────────────────────────────────────────────────
var currentProjetId = null;
var currentProjetData = {};
var notesSaveTimer = null;

// ── LISTE DES PROJETS ─────────────────────────────────────────────────
async function loadV360Sessions() {
  var list = document.getElementById('v360-sessions-list');
  try {
    var res = await fetch(API + '/api/veille360/sessions');
    var sessions = await res.json();
    document.getElementById('v360-sessions-count').textContent = sessions.length + ' projet' + (sessions.length > 1 ? 's' : '');
    if (!sessions.length) {
      list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🗂</div><div class="empty-state-title">Aucun dossier</div><p>Créez votre premier projet client.</p></div>';
      return;
    }
    list.innerHTML = sessions.map(function(s) {
      var date = s.created_at ? new Date(s.created_at).toLocaleDateString('fr-FR') : '';
      var desc = (s.project_desc||'').slice(0,80) + ((s.project_desc||'').length > 80 ? '…' : '');
      return '<div class="ep-project-card" data-sid="' + s.id + '" onclick="openProjetById(this)">' +
        '<div class="ep-project-card-icon">🗂</div>' +
        '<div class="ep-project-card-main">' +
          '<div class="ep-project-card-client">' + (s.client_name||'Sans nom') + '</div>' +
          '<div class="ep-project-card-desc">' + desc + '</div>' +
          '<div class="ep-project-card-meta">' + date + '</div>' +
        '</div>' +
        '<div class="ep-project-card-actions">' +
          '<button class="ep-del-btn" data-sid="' + s.id + '" onclick="deleteProjetById(event,this)">✕</button>' +
        '</div></div>';
    }).join('');
  } catch(e) { list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠️</div><div class="empty-state-title">Erreur</div></div>'; }
}

// ── CRÉER / OUVRIR / FERMER ────────────────────────────────────────────
function openNewProjet() {
  document.getElementById('ep-new-client').value = '';
  document.getElementById('ep-new-desc').value = '';
  document.getElementById('ep-new-modal').style.display = 'flex';
  setTimeout(function(){ document.getElementById('ep-new-client').focus(); }, 100);
}
function closeNewProjet() { document.getElementById('ep-new-modal').style.display = 'none'; }

async function createProjet() {
  var client = document.getElementById('ep-new-client').value.trim();
  var desc   = document.getElementById('ep-new-desc').value.trim();
  if (!client) { document.getElementById('ep-new-client').focus(); return; }
  var res = await fetch(API + '/api/veille360/sessions', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({client_name: client, project_desc: desc, result_html: ''})
  });
  var data = await res.json();
  closeNewProjet();
  await loadV360Sessions();
  openProjet(data.id || data.session_id);
}

async function openProjet(id) {
  var res = await fetch(API + '/api/veille360/sessions/' + id);
  var session = await res.json();
  currentProjetId = id;
  currentProjetData = session;
  document.getElementById('ep-client-name').textContent = session.client_name || 'Projet';
  document.getElementById('ep-project-desc').textContent = session.project_desc || '';
  document.getElementById('v360-project').value = session.project_desc || '';
  document.getElementById('ep-notes-area').value = session.notes || '';
  document.getElementById('v360-modal-body').innerHTML = session.result_html || '<p style="color:var(--muted);font-size:12px;">Lancez une analyse 360° pour identifier les dispositifs potentiels.</p>';
  document.getElementById('ep-list-view').style.display = 'none';
  document.getElementById('ep-detail-view').style.display = 'block';
  switchEpTab('analyse', document.getElementById('ept-analyse'));
  loadProjetShortlist();
}

function closeProjetDetail() {
  document.getElementById('ep-detail-view').style.display = 'none';
  document.getElementById('ep-list-view').style.display = 'block';
  currentProjetId = null;
  loadV360Sessions();
}

async function deleteProjet(e, id) {
  e.stopPropagation();
  if (!confirm('Supprimer ce dossier ?')) return;
  await fetch(API + '/api/veille360/sessions/' + id, {method:'DELETE'});
  loadV360Sessions();
}

// ── ONGLETS PROJET ─────────────────────────────────────────────────────
function switchEpTab(tab, btn) {
  document.querySelectorAll('.ep-tab').forEach(function(b){ b.classList.remove('active'); });
  document.querySelectorAll('.ep-pane').forEach(function(p){ p.classList.remove('active'); });
  if (btn) btn.classList.add('active');
  document.getElementById('ep-pane-' + tab).classList.add('active');
  if (tab === 'shortlist') loadProjetShortlist();
}

// ── ANALYSE 360° ───────────────────────────────────────────────────────
async function runV360() {
  if (!currentProjetId) return;
  var project = document.getElementById('v360-project').value.trim();
  if (!project) { document.getElementById('v360-project').focus(); return; }
  var btn = document.getElementById('v360-run-btn');
  btn.disabled = true; btn.textContent = '⏳ Analyse…';
  document.getElementById('v360-status-inline').textContent = 'Analyse en cours — environ 20 secondes…';
  try {
    var res = await fetch(API + '/api/veille360', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({project_desc: project, client_name: currentProjetData.client_name || ''})
    });
    var data = await res.json();
    if (data.error) throw new Error(data.error);
    // Enrichir le HTML avec boutons Collecter
    var enriched = enrichV360Result(data.result_html || data.html || '');
    document.getElementById('v360-modal-body').innerHTML = enriched;
    document.getElementById('v360-status-inline').textContent = '';
    // Sauvegarder
    await fetch(API + '/api/veille360/sessions', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({client_name: currentProjetData.client_name, project_desc: project, result_html: enriched, id: currentProjetId})
    });
  } catch(err) {
    document.getElementById('v360-status-inline').textContent = '⚠ Erreur : ' + err.message;
  }
  btn.disabled = false; btn.textContent = '🔍 Analyser';
}

function enrichV360Result(html) {
  // Ajouter bouton "Retenir" sur chaque ligne de dispositif dans le tableau 360°
  return html.replace(/<tr>/g, '<tr class="v360-row">').replace(/<\/tr>/g, function(match, offset, str) {
    // Récupérer le titre de la ligne
    return '<td><button class="v360-collect-btn" onclick="retainFromV360(this)">⭐ Retenir</button></td></tr>';
  });
}

async function retainFromV360(btn) {
  if (!currentProjetId) return;
  btn.disabled = true; btn.textContent = '⏳…';
  var row = btn.closest('tr');
  var cells = row ? row.querySelectorAll('td') : [];
  var titre = cells[0] ? cells[0].textContent.trim() : '';
  var financeur = cells[1] ? cells[1].textContent.trim() : '';
  var nature = cells[2] ? cells[2].textContent.trim() : '';
  var territoire = cells[3] ? cells[3].textContent.trim() : '';
  var montants = cells[4] ? cells[4].textContent.trim() : '';
  var res = await fetch(API + '/api/veille360/sessions/' + currentProjetId + '/dispositifs', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({titre:titre, guichet_financeur:financeur, nature:nature, territoire:territoire, montants_taux:montants, statut:'identifie'})
  });
  var data = await res.json();
  if (data.status === 'duplicate') { btn.textContent = '✓ Déjà retenu'; }
  else { btn.className = 'v360-collect-btn done'; btn.textContent = '✓ Retenu'; }
}

// ── SHORTLIST / KANBAN ─────────────────────────────────────────────────
async function loadProjetShortlist() {
  if (!currentProjetId) return;
  var res = await fetch(API + '/api/veille360/sessions/' + currentProjetId + '/dispositifs');
  var disps = await res.json();
  var cols = {identifie:[], en_cours:[], depose:[]};
  disps.forEach(function(d){ if (cols[d.statut]) cols[d.statut].push(d); else cols['identifie'].push(d); });
  Object.keys(cols).forEach(function(statut) {
    var el = document.getElementById('ep-col-' + statut);
    if (!el) return;
    if (!cols[statut].length) { el.innerHTML = '<div style="font-size:11px;color:var(--muted2);text-align:center;padding:12px;">Aucun dispositif</div>'; return; }
    el.innerHTML = cols[statut].map(function(d) {
      return '<div class="ep-disp-card">' +
        '<div class="ep-disp-card-title">' + (d.titre||'Sans titre') + '</div>' +
        '<div class="ep-disp-card-fin">' + (d.guichet_financeur||'') + (d.nature?' · '+d.nature:'') + '</div>' +
        (d.montants_taux ? '<div style="font-size:10px;color:var(--accent);font-weight:700;">' + d.montants_taux.slice(0,60) + '</div>' : '') +
        '<div class="ep-disp-card-actions">' +
          '<select class="ep-statut-sel" data-did="' + d.id + '" onchange="changeStatutById(this)">' +
            '<option value="identifie"' + (d.statut==='identifie'?' selected':'') + '>🔵 Identifié</option>' +
            '<option value="en_cours"' + (d.statut==='en_cours'?' selected':'') + '>🟡 En cours</option>' +
            '<option value="depose"' + (d.statut==='depose'?' selected':'') + '>🟢 Déposé</option>' +
          '</select>' +
          '<button class="ep-disp-btn pptx" data-did="' + d.id + '" onclick="collectFromShortlistById(this)">📋 Fiche complète</button>' +
          '<button class="ep-disp-btn email" data-did="' + d.id + '" onclick="generateEmailById(this)">📧 Contact</button>' +
          '<button class="ep-disp-btn del" data-did="' + d.id + '" onclick="removeFromShortlistById(this)">✕</button>' +
        '</div></div>';
    }).join('');
  });
}

async function changeStatut(sel, did) {
  await fetch(API + '/api/veille360/sessions/' + currentProjetId + '/dispositifs/' + did, {
    method:'PATCH', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({statut: sel.value})
  });
  setTimeout(loadProjetShortlist, 200);
}

async function removeFromShortlist(did) {
  await fetch(API + '/api/veille360/sessions/' + currentProjetId + '/dispositifs/' + did, {method:'DELETE'});
  loadProjetShortlist();
}

// ── EMAIL DE CONTACT ───────────────────────────────────────────────────
async function generateEmail(did) {
  showToast('Génération email contact...');
  var res_d = await fetch(API + '/api/veille360/sessions/' + currentProjetId + '/dispositifs');
  var disps = await res_d.json();
  var disp = disps.find(function(d){ return d.id === did; });
  if (!disp) return;
  var res = await fetch(API + '/api/veille360/sessions/' + currentProjetId + '/contact', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({dispositif: disp, client_name: currentProjetData.client_name, project_desc: currentProjetData.project_desc})
  });
  var data = await res.json();
  document.getElementById('ep-email-content').value = data.email || data.error || '';
  document.getElementById('ep-email-modal').style.display = 'flex';
}

function copyEmail() {
  var ta = document.getElementById('ep-email-content');
  navigator.clipboard.writeText(ta.value).then(function(){ showToast('Email copié !'); });
}

// ── EXPORT PPTX SHORTLIST ─────────────────────────────────────────────
async function collectFromShortlist(btn, did) {
  if (!currentProjetId) return;
  btn.disabled = true; btn.textContent = '⏳…';
  // Récupérer les infos du dispositif shortlist
  var res_d = await fetch(API + '/api/veille360/sessions/' + currentProjetId + '/dispositifs');
  var disps = await res_d.json();
  var disp = disps.find(function(d){ return d.id === did; });
  if (!disp || !disp.source_url) { btn.disabled=false; btn.textContent='📋 Fiche complète'; showToast('URL source manquante'); return; }
  try {
    // Appel /api/collect pour enrichir la fiche via Claude
    var res = await fetch(API + '/api/collect', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({url: disp.source_url, title: disp.titre, id: 0, pdf_url: ''})
    });
    var data = await res.json();
    if (data.error) throw new Error(data.error);
    // Sauvegarder dans dispositifs globaux
    var res2 = await fetch(API + '/api/dispositifs', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(data)
    });
    var saved = await res2.json();
    // Mettre à jour la carte shortlist avec les données enrichies
    await fetch(API + '/api/veille360/sessions/' + currentProjetId + '/dispositifs/' + did, {
      method:'PATCH', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        statut: disp.statut,
        notes: 'Fiche collectée le ' + new Date().toLocaleDateString('fr-FR'),
        contact: data.contact || disp.contact || ''
      })
    });
    btn.textContent = '✅ Collecté';
    btn.style.cssText = 'background:rgba(62,207,122,.12);border-color:rgba(62,207,122,.4);color:#1a7a40;';
    showToast('Fiche complète collectée !');
    if (saved.id) {
      // Bouton PPTX apparaît
      var actionsDiv = btn.parentElement;
      var pptxBtn = document.createElement('button');
      pptxBtn.className = 'ep-disp-btn pptx';
      pptxBtn.textContent = '📊 PPTX';
      pptxBtn.onclick = function(){ window.open(API + '/api/dispositifs/' + saved.id + '/export-pptx', '_blank'); };
      actionsDiv.insertBefore(pptxBtn, btn.nextSibling);
    }
  } catch(e) {
    btn.disabled = false; btn.textContent = '📋 Fiche complète';
    showToast('Erreur : ' + e.message);
  }
}

function exportDispPptxFromShortlist(did) {
  window.open(API + '/api/dispositifs/' + did + '/export-pptx', '_blank');
}

async function exportProjetPptx() {
  showToast('Export en cours…');
  // Récupérer tous les dispositifs et exporter le premier (à étendre)
  var res = await fetch(API + '/api/veille360/sessions/' + currentProjetId + '/dispositifs');
  var disps = await res.json();
  if (!disps.length) { showToast('Aucun dispositif dans la shortlist'); return; }
  // Pour l'instant : ouvrir le PPTX du premier dispositif retenu
  disps.forEach(function(d, i){ setTimeout(function(){ window.open(API + '/api/dispositifs/' + d.id + '/export-pptx', '_blank'); }, i*500); });
}

// ── NOTES ──────────────────────────────────────────────────────────────
function autoSaveNotes() {
  clearTimeout(notesSaveTimer);
  document.getElementById('ep-notes-saved').textContent = '…';
  notesSaveTimer = setTimeout(async function(){
    var notes = document.getElementById('ep-notes-area').value;
    await fetch(API + '/api/veille360/sessions/' + currentProjetId + '/notes', {
      method:'PATCH', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({notes: notes})
    });
    document.getElementById('ep-notes-saved').textContent = '✓ Sauvegardé';
    setTimeout(function(){ document.getElementById('ep-notes-saved').textContent = ''; }, 2000);
  }, 1500);
}


init();
</script>
</body>
</html>
"""


HTML_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,400&display=swap" rel="stylesheet">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SubstanCiel — Veille Subventions</title>
<style>
/* ═══════════════════════════════════════════
   SUBSTANCIEL — Design System v3
   Palette: Forest Green + Lime + Bone White
   Typography: Syne (display) + DM Sans (text)
═══════════════════════════════════════════ */

:root {
  --bg: #f2f4f0;
  --surface: #ffffff;
  --surface2: #f7f8f5;
  --surface3: #eef0ea;
  --border: #e0e5d8;
  --border2: #d0d8c4;

  --accent: #1a3c2e;
  --accent2: #2a5c46;
  --accent3: #3d7a5e;
  --lime: #c8e84e;
  --lime2: #b0d035;
  --lime-bg: rgba(200,232,78,0.12);

  --gold: #d4900a;
  --green: #1e8f54;
  --red: #c8392b;
  --purple: #6241a8;
  --blue: #1a6fa8;
  --orange: #d4620a;

  --text: #111a14;
  --text2: #3a4a3e;
  --muted: #7a8e80;
  --muted2: #a0b0a4;

  --shadow-xs: 0 1px 3px rgba(26,60,46,0.06);
  --shadow: 0 2px 8px rgba(26,60,46,0.08);
  --shadow-md: 0 4px 20px rgba(26,60,46,0.12);
  --shadow-lg: 0 8px 40px rgba(26,60,46,0.16);

  --radius-sm: 6px;
  --radius: 10px;
  --radius-lg: 14px;
  --radius-xl: 18px;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: 'DM Sans', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  font-size: 13px;
  -webkit-font-smoothing: antialiased;
}

/* ─── TITLEBAR ──────────────────────────── */
.titlebar {
  height: 48px;
  background: var(--accent);
  background-image: linear-gradient(135deg, #1a3c2e 0%, #1f4a38 100%);
  border-bottom: 1px solid rgba(200,232,78,0.2);
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 14px;
  flex-shrink: 0;
  position: relative;
  z-index: 20;
  box-shadow: 0 1px 0 rgba(200,232,78,0.15);
}
.logo {
  font-family: 'Syne', sans-serif;
  font-size: 17px;
  font-weight: 800;
  color: #fff;
  letter-spacing: -0.04em;
  display: flex;
  align-items: center;
  gap: 1px;
}
.logo em { color: var(--lime); font-style: normal; }
.logo-dot { width: 5px; height: 5px; background: var(--lime); border-radius: 50%; margin-left: 1px; margin-bottom: 6px; display: inline-block; }

.live-badge {
  display: flex; align-items: center; gap: 5px;
  background: rgba(200,232,78,0.12);
  border: 1px solid rgba(200,232,78,0.25);
  border-radius: 100px;
  padding: 3px 10px 3px 8px;
  font-size: 10px;
  color: rgba(200,232,78,0.85);
  font-weight: 600;
  letter-spacing: 0.02em;
}
.live-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--lime);
  animation: pulse 2s infinite;
}
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.5;transform:scale(0.8)} }

.titlebar-stats {
  margin-left: auto;
  display: flex; gap: 20px; align-items: center;
}
.ts-item {
  font-size: 11px;
  color: rgba(255,255,255,0.45);
  display: flex; align-items: center; gap: 6px;
}
.ts-val {
  color: rgba(255,255,255,0.85);
  font-weight: 700;
  font-family: 'Syne', sans-serif;
  font-size: 12px;
}
.ts-accent { color: var(--lime); }
.ts-divider { width: 1px; height: 14px; background: rgba(255,255,255,0.1); }

.scrape-btn {
  background: var(--lime);
  border: none;
  color: var(--accent);
  padding: 6px 14px;
  border-radius: 100px;
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
  transition: all 0.15s;
  font-family: 'Syne', sans-serif;
  letter-spacing: -0.01em;
}
.scrape-btn:hover { background: var(--lime2); transform: translateY(-1px); box-shadow: 0 3px 10px rgba(200,232,78,0.4); }

/* ─── TABS ──────────────────────────────── */
.tabs-bar {
  background: var(--accent);
  background-image: linear-gradient(135deg, #1a3c2e 0%, #1f4a38 100%);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  padding: 0 20px;
  display: flex; align-items: flex-end; gap: 1px;
  flex-shrink: 0;
  height: 38px;
}
.tab-btn {
  padding: 7px 16px;
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  font-family: 'DM Sans', sans-serif;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  color: rgba(255,255,255,0.45);
  transition: all 0.15s;
  border: none;
  background: none;
  position: relative;
  bottom: 0;
  white-space: nowrap;
  letter-spacing: 0.01em;
}
.tab-btn:hover { color: rgba(255,255,255,0.75); background: rgba(255,255,255,0.06); }
.tab-btn.active {
  background: var(--bg);
  color: var(--accent);
  font-weight: 700;
  border: 1px solid var(--border);
  border-bottom-color: var(--bg);
}
.tab-icon { margin-right: 5px; font-size: 12px; }

/* ─── LAYOUT ────────────────────────────── */
.app { display: flex; flex: 1; overflow: hidden; }

/* ─── SIDEBAR ───────────────────────────── */
.sidebar {
  width: 230px;
  flex-shrink: 0;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.sidebar-top {
  padding: 10px 10px 6px;
  border-bottom: 1px solid var(--border);
  background: var(--surface2);
  flex-shrink: 0;
}
.sidebar-actions {
  display: flex; gap: 4px;
  padding: 6px 0 2px;
}
.sidebar-action-btn {
  flex: 1;
  background: none;
  border: 1px solid var(--border);
  color: var(--muted);
  font-size: 10px; font-weight: 700;
  padding: 4px 6px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-family: 'DM Sans', sans-serif;
  transition: all 0.15s;
  letter-spacing: 0.01em;
}
.sidebar-action-btn:hover {
  background: var(--surface3);
  border-color: var(--accent3);
  color: var(--accent);
}
/* ─── CREATE FOLDER MODAL ─────────── */
.cf-box {
  width: 380px;
  border-radius: var(--radius-xl);
  overflow: hidden;
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: 0 24px 60px rgba(17,26,20,0.18);
}
.cf-header {
  display: flex; align-items: center; gap: 10px;
  padding: 18px 20px 14px;
  background: var(--surface2);
  border-bottom: 1px solid var(--border);
}
.cf-icon { font-size: 20px; flex-shrink: 0; }
.cf-title {
  flex: 1;
  font-family: 'Syne', sans-serif;
  font-size: 15px; font-weight: 800;
  color: var(--accent);
}
.cf-close {
  background: none; border: 1px solid var(--border);
  color: var(--muted); width: 26px; height: 26px;
  border-radius: var(--radius-sm); cursor: pointer;
  font-size: 12px; display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.cf-close:hover { background: var(--surface3); color: var(--accent); }
.cf-body {
  padding: 20px;
  display: flex; flex-direction: column; gap: 14px;
}
.cf-label {
  font-size: 10px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.1em;
  color: var(--muted); display: block; margin-bottom: 5px;
}
.cf-input {
  width: 100%; box-sizing: border-box;
  background: var(--surface2);
  border: 1.5px solid var(--border);
  color: var(--text); padding: 9px 12px;
  border-radius: var(--radius-sm);
  font-size: 13px; font-family: 'DM Sans', sans-serif;
  outline: none; transition: all 0.15s;
}
.cf-input:focus { border-color: var(--accent3); box-shadow: 0 0 0 3px rgba(26,60,46,0.08); }
.cf-input::placeholder { color: var(--muted2); }
.cf-footer {
  padding: 14px 20px;
  border-top: 1px solid var(--border);
  display: flex; gap: 8px; justify-content: flex-end;
  background: var(--surface2);
}
/* ─── DELETE FOLDER MODAL ─────────── */
.df-box {
  width: 420px;
  border-radius: var(--radius-xl);
  overflow: hidden;
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: 0 24px 60px rgba(17,26,20,0.2);
}
.df-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px;
  background: var(--surface2);
  border-bottom: 1px solid var(--border);
}
.df-title {
  font-family: 'Syne', sans-serif;
  font-size: 14px; font-weight: 800;
  color: var(--accent);
}
.df-body {
  padding: 16px;
  display: flex; flex-direction: column; gap: 10px;
}
.df-option {
  display: flex; align-items: flex-start; gap: 14px;
  padding: 14px 16px;
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all 0.15s;
  background: var(--surface);
}
.df-option:hover {
  border-color: var(--accent3);
  background: rgba(26,60,46,0.03);
  transform: translateX(2px);
}
.df-option-danger {
  border-color: rgba(200,57,43,0.2);
  background: rgba(200,57,43,0.02);
}
.df-option-danger:hover {
  border-color: rgba(200,57,43,0.5);
  background: rgba(200,57,43,0.06);
  transform: translateX(2px);
}
.df-opt-icon { font-size: 22px; flex-shrink: 0; margin-top: 1px; }
.df-opt-content { flex: 1; }
.df-opt-title {
  font-size: 13px; font-weight: 700;
  color: var(--text); margin-bottom: 3px;
}
.df-option-danger .df-opt-title { color: #c8392b; }
.df-opt-desc { font-size: 11px; color: var(--muted); line-height: 1.45; }
.df-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  display: flex; justify-content: flex-end;
  background: var(--surface2);
}
.sidebar-search { position: relative; }
.sidebar-search input {
  width: 100%;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 7px 10px 7px 30px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-family: 'DM Sans', sans-serif;
  outline: none;
  transition: all 0.15s;
}
.sidebar-search input:focus { border-color: var(--accent3); box-shadow: 0 0 0 2px rgba(26,60,46,0.08); }
.sidebar-search input::placeholder { color: var(--muted2); }
.sidebar-search-icon { position: absolute; left: 9px; top: 50%; transform: translateY(-50%); font-size: 11px; color: var(--muted); }
.nav-scroll { flex: 1; overflow-y: auto; padding: 6px 0; }

/* NAV ALL */
.nav-all {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px 7px 12px;
  border-radius: var(--radius);
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
  transition: all 0.12s;
  border: 1px solid transparent;
}
.nav-all:hover { background: var(--surface2); }
.nav-all.active {
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%);
  color: var(--lime);
  border-color: transparent;
}
.nav-all-icon { font-size: 13px; }
.nav-all-count {
  margin-left: auto;
  font-size: 10px;
  font-weight: 700;
  background: rgba(255,255,255,0.15);
  padding: 1px 7px;
  border-radius: 100px;
  color: inherit;
  opacity: 0.8;
}
.nav-all:not(.active) .nav-all-count {
  background: var(--surface3);
  border: 1px solid var(--border);
  color: var(--muted);
}

/* NAV CATEGORIES */
.nav-cat { margin: 1px 0; }
.nav-cat-header {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px 7px 14px;
  margin: 0 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.12s;
  border: 1px solid transparent;
}
.nav-cat-header:hover { background: var(--surface2); border-color: var(--border); }
.nav-cat-header.active {
  background: rgba(26,60,46,0.07);
  border-color: rgba(26,60,46,0.15);
  color: var(--accent);
}
.nav-cat-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.nav-cat-name { font-size: 11px; font-weight: 600; color: var(--text); flex: 1; }
.nav-cat-count {
  font-size: 10px;
  font-weight: 700;
  color: var(--muted);
  background: var(--surface3);
  border: 1px solid var(--border);
  border-radius: 100px;
  padding: 0px 6px;
  min-width: 22px; text-align: center;
}
.nav-cat-arrow {
  font-size: 9px; color: var(--muted2);
  transition: transform 0.2s;
  width: 12px; text-align: center;
}
.nav-cat-arrow.open { transform: rotate(90deg); }

/* NAV REGIONS */
.nav-regions { display: none; padding: 0 0 2px 0; }
.nav-regions.open { display: block; }
.nav-region {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 10px 5px 34px;
  margin: 0 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.12s;
  font-size: 11px;
  color: var(--text2);
  border: 1px solid transparent;
}
.nav-region:hover { background: var(--surface2); border-color: var(--border); }
.nav-region.active {
  background: rgba(26,60,46,0.08);
  color: var(--accent);
  font-weight: 600;
  border-color: rgba(26,60,46,0.18);
}
.nav-region-name { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.nav-region-count {
  font-size: 10px;
  font-weight: 700;
  color: var(--muted2);
}
.nav-region.active .nav-region-count { color: var(--accent3); }

/* SIDEBAR BOTTOM */
.sidebar-bottom {
  padding: 10px 14px;
  border-top: 1px solid var(--border);
  background: var(--surface2);
  flex-shrink: 0;
}
.mini-stat {
  display: flex; justify-content: space-between; align-items: center;
  padding: 3px 0; font-size: 10px;
}
.mini-label { color: var(--muted); }
.mini-value { font-weight: 700; font-family: 'Syne', sans-serif; font-size: 11px; }

/* ─── MAIN AREA ─────────────────────────── */
.main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

/* ─── TOOLBAR ───────────────────────────── */
.toolbar {
  padding: 9px 16px;
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 8px;
  flex-shrink: 0;
  background: var(--surface);
  box-shadow: var(--shadow-xs);
}
.search-wrap { position: relative; flex: 1; max-width: 360px; }
.search-wrap input {
  width: 100%;
  background: var(--surface2);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 7px 12px 7px 32px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-family: 'DM Sans', sans-serif;
  outline: none;
  transition: all 0.15s;
}
.search-wrap input:focus { border-color: var(--accent3); background: var(--surface); box-shadow: 0 0 0 3px rgba(26,60,46,0.08); }
.search-icon { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--muted); font-size: 13px; }
.filter-chips { display: flex; gap: 5px; align-items: center; flex-wrap: wrap; }
.chip {
  padding: 5px 11px;
  border-radius: 100px;
  font-size: 10px;
  font-weight: 700;
  cursor: pointer;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--muted);
  transition: all 0.12s;
  font-family: 'DM Sans', sans-serif;
  letter-spacing: 0.01em;
}
.chip:hover { border-color: var(--accent3); color: var(--accent); }
.chip.active { background: var(--accent); color: var(--lime); border-color: var(--accent); }

.breadcrumb {
  font-size: 11px; color: var(--muted);
  display: flex; align-items: center; gap: 5px;
}
.breadcrumb strong { color: var(--accent); font-weight: 700; }

/* ─── STATS ROW ─────────────────────────── */
.stats-row {
  display: flex; gap: 0;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
}
.stat-box {
  flex: 1;
  text-align: center;
  padding: 10px 12px;
  border-right: 1px solid var(--border);
  position: relative;
}
.stat-box:last-child { border-right: none; }
.stat-lbl {
  font-size: 9px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 4px;
  font-weight: 700;
}
.stat-val {
  font-family: 'Syne', sans-serif;
  font-size: 20px;
  font-weight: 800;
  color: var(--accent);
  line-height: 1;
}

/* ─── TAG BAR ───────────────────────────── */
.tag-bar-wrapper {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.tag-bar-header {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 16px 0;
}
.tag-bar-toggle {
  background: none;
  border: 1px solid var(--border);
  color: var(--muted);
  cursor: pointer;
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 4px;
  transition: all 0.15s;
}
.tag-bar-toggle:hover { color: var(--accent); border-color: var(--accent3); }
.tag-bar-label {
  font-size: 9px; color: var(--muted); font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.1em;
}
.tagged-only-btn {
  font-size: 10px; padding: 3px 10px; border-radius: 100px;
  border: 1px solid var(--border);
  background: none; color: var(--muted);
  cursor: pointer; font-weight: 700; transition: all 0.15s;
  margin-left: auto; font-family: 'DM Sans', sans-serif;
}
.tagged-only-btn.active { background: var(--accent); color: var(--lime); border-color: var(--accent); }
.tag-bar {
  display: flex; gap: 5px; flex-wrap: wrap;
  padding: 7px 16px 9px;
  overflow-x: auto;
}
.tag-pill {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px;
  border-radius: 100px;
  font-size: 10px; font-weight: 700;
  cursor: pointer;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--muted);
  transition: all 0.12s;
  white-space: nowrap;
  font-family: 'DM Sans', sans-serif;
}
.tag-pill:hover { border-color: var(--accent3); color: var(--accent); background: rgba(26,60,46,0.04); }
.tag-pill.active { background: var(--accent); color: var(--lime); border-color: var(--accent); }
.tag-star { font-size: 9px; }

/* ─── SELECTION BAR ─────────────────────── */
.toolbar-sel {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 14px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
}
.sel-divider { width: 1px; height: 16px; background: var(--border); margin: 0 4px; }
.sel-dropdown-wrap { position: relative; }
.sel-filter-btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; border-radius: 100px;
  font-size: 11px; font-weight: 600;
  cursor: pointer; border: 1.5px solid var(--border);
  background: var(--surface2); color: var(--text);
  transition: all 0.15s; font-family: "DM Sans", sans-serif;
}
.sel-filter-btn:hover { border-color: var(--accent3); }
.sel-filter-btn.has-active { border-color: var(--lime); background: var(--accent); color: var(--lime); }
.sel-dropdown {
  display: none; position: fixed; z-index: 9999;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); box-shadow: var(--shadow-lg);
  min-width: 200px; overflow: hidden;
}
.sel-dropdown.open { display: block; }
.sel-drop-item {
  padding: 9px 14px; font-size: 12px; cursor: pointer;
  display: flex; align-items: center; gap: 8px;
  color: var(--text); transition: background 0.1s;
  font-family: "DM Sans", sans-serif;
}
.sel-drop-item:hover { background: var(--surface2); }
.sel-drop-item.active { color: var(--accent); font-weight: 700; }
.sel-drop-check { font-size: 14px; width: 16px; }
.sel-toggle-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 12px;
  border-radius: 100px;
  font-size: 11px; font-weight: 700;
  cursor: pointer;
  border: 1.5px solid var(--border);
  background: var(--surface2);
  color: var(--text);
  transition: all 0.15s;
  font-family: 'DM Sans', sans-serif;
  letter-spacing: 0.01em;
}
.sel-toggle-btn:hover { border-color: var(--accent3); color: var(--accent); background: rgba(26,60,46,0.05); }
.sel-toggle-btn.active {
  background: var(--accent); border-color: var(--accent); color: var(--lime);
}
.sel-count-badge {
  font-size: 11px; color: var(--muted);
  font-family: 'DM Sans', sans-serif;
  font-weight: 500;
  flex: 1;
}
.sel-count-badge strong { color: var(--accent); font-weight: 700; }
.btn-tag-sel {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 12px;
  border-radius: 100px;
  font-size: 11px; font-weight: 700;
  cursor: pointer;
  border: 1.5px solid var(--accent);
  background: var(--accent);
  color: var(--lime);
  transition: all 0.15s;
  font-family: 'DM Sans', sans-serif;
}
.btn-tag-sel:hover { opacity: 0.88; }
.btn-tag-sel:disabled { opacity: 0.35; cursor: not-allowed; }
.btn:hover { background: var(--surface2); border-color: var(--accent3); color: var(--accent); }
.btn-primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--lime);
}
.btn-primary:hover { background: var(--accent2); border-color: var(--accent2); color: white; }
.btn-lime {
  background: var(--lime);
  border-color: var(--lime2);
  color: var(--accent);
}
.btn-lime:hover { background: var(--lime2); }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* ─── FEED ──────────────────────────────── */
.feed-area { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
.feed-header {
  padding: 9px 16px;
  display: flex; align-items: center; gap: 8px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
}
.feed-title {
  font-family: 'Syne', sans-serif;
  font-size: 13px;
  font-weight: 800;
  color: var(--accent);
  display: flex; align-items: center; gap: 6px;
}
.feed-meta { font-size: 10px; color: var(--muted); margin-left: auto; }
.feed {
  flex: 1; overflow-y: auto;
  padding: 12px 14px;
  display: flex; flex-direction: column; gap: 7px;
}

/* ─── CARDS ─────────────────────────────── */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.15s;
  position: relative;
  box-shadow: var(--shadow-xs);
}
.card:hover {
  border-color: var(--accent3);
  box-shadow: var(--shadow);
  transform: translateY(-1px);
}
.card.selected {
  border-color: var(--accent);
  background: rgba(26,60,46,0.025);
  box-shadow: 0 0 0 2px rgba(26,60,46,0.08);
}
.card-top { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 6px; }
.card-check { flex-shrink: 0; margin-top: 3px; accent-color: var(--accent); }
.card-title {
  font-size: 13px; font-weight: 700; line-height: 1.38;
  color: var(--text); flex: 1;
}
.card-title a { color: inherit; text-decoration: none; }
.card-title a:hover { color: var(--accent2); }
.card-meta {
  display: flex; align-items: center; gap: 8px;
  font-size: 10px; color: var(--muted);
  flex-wrap: wrap; margin-top: 1px;
}
.card-source { font-weight: 700; color: var(--accent3); }
.card-sep { color: var(--border2); }
.card-region-badge {
  background: var(--surface3);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 10px;
  color: var(--text2);
  font-weight: 600;
}
.card-tags { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 6px; }
.card-tag {
  font-size: 9px; padding: 2px 8px;
  border-radius: 100px;
  font-weight: 700;
  background: rgba(26,60,46,0.06);
  color: var(--accent);
  border: 1px solid rgba(26,60,46,0.12);
  letter-spacing: 0.01em;
}
.card-tag.star {
  background: rgba(200,232,78,0.2);
  color: #4a6800;
  border-color: rgba(200,232,78,0.5);
}
.card-summary { font-size: 11px; color: var(--muted); line-height: 1.55; margin-top: 5px; }

/* ─── STATE BOX ─────────────────────────── */
.state-box {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 60px 20px; gap: 12px;
  color: var(--muted); text-align: center;
}
.spinner {
  width: 24px; height: 24px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg) } }
.state-box p { font-size: 12px; color: var(--muted2); }

/* ─── 3-DOT MENU ────────────────────────── */
.card-menu-wrap { position: relative; display: flex; flex-direction: column; gap: 5px; align-items: center; }
.card-pdf-btn {
  display: flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border-radius: 6px;
  font-size: 15px; text-decoration: none; cursor: pointer;
  background: var(--surface); border: 1px solid var(--border);
  transition: background 0.15s, border-color 0.15s;
}
.card-pdf-btn:hover { background: var(--surface2); border-color: var(--accent); }
.card-pdf-empty { opacity: 0.25; cursor: default; pointer-events: none; }
.card-menu-btn {
  width: 26px; height: 26px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--muted); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; transition: all 0.15s; flex-shrink: 0;
}
.card-menu-btn:hover { background: var(--surface); border-color: var(--accent3); color: var(--accent); }
.card-menu {
  display: none;
  position: fixed;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  min-width: 185px; z-index: 9999;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}
.card-menu.open { display: block; }
.card-menu-item {
  padding: 9px 14px; font-size: 11px;
  cursor: pointer; color: var(--text);
  display: flex; align-items: center; gap: 9px;
  transition: background 0.1s; font-weight: 500;
}
.card-menu-item:hover { background: var(--surface2); color: var(--accent); }
.card-menu-sep { height: 1px; background: var(--border); }

/* ─── SOURCES PANEL ─────────────────────── */
.src-panel { display: none; flex: 1; flex-direction: column; overflow: hidden; }
.src-panel.active { display: flex; }
.src-topbar {
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0; box-shadow: var(--shadow-xs);
}
.src-title { font-family: 'Syne', sans-serif; font-size: 15px; font-weight: 800; color: var(--accent); }
.src-sub { font-size: 11px; color: var(--muted); margin-top: 2px; }
.src-body { flex: 1; overflow-y: auto; padding: 16px 20px; }
.add-src-form {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: 16px;
  margin-bottom: 16px; box-shadow: var(--shadow-xs);
}
.add-src-title { font-size: 12px; font-weight: 700; color: var(--accent); margin-bottom: 12px; font-family: 'Syne', sans-serif; }
.form-row { display: flex; gap: 8px; flex-wrap: wrap; align-items: flex-end; }
.form-field { display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 120px; }
.form-label { font-size: 10px; color: var(--muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; }
.form-input {
  background: var(--surface2); border: 1px solid var(--border);
  color: var(--text); padding: 7px 10px;
  border-radius: var(--radius-sm); font-size: 11px;
  font-family: 'DM Sans', sans-serif; outline: none;
  transition: all 0.15s;
}
.form-input:focus { border-color: var(--accent3); box-shadow: 0 0 0 2px rgba(26,60,46,0.07); }
.form-select {
  background: var(--surface2); border: 1px solid var(--border);
  color: var(--text); padding: 7px 10px;
  border-radius: var(--radius-sm); font-size: 11px;
  font-family: 'DM Sans', sans-serif; outline: none; cursor: pointer;
}
.src-grid { display: flex; flex-direction: column; gap: 5px; }
.src-row {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 10px 14px;
  display: flex; align-items: center; gap: 10px;
  font-size: 11px; transition: all 0.12s;
}
.src-row:hover { border-color: var(--accent3); box-shadow: var(--shadow-xs); }
.src-name { font-weight: 600; color: var(--text); flex: 1; }
.src-badge {
  font-size: 9px; padding: 2px 8px;
  border-radius: 100px; font-weight: 700;
}
.src-badge.ok { background: rgba(30,143,84,0.1); color: var(--green); border: 1px solid rgba(30,143,84,0.2); }
.src-badge.err { background: rgba(200,57,43,0.08); color: var(--red); border: 1px solid rgba(200,57,43,0.18); }
.src-badge.dyn { background: var(--lime-bg); color: #4a6800; border: 1px solid rgba(200,232,78,0.4); }
.src-meta { font-size: 10px; color: var(--muted); }

/* ─── DASHBOARD PANEL ───────────────────── */
.dash-panel { display: none; flex: 1; flex-direction: column; overflow: hidden; }
.dash-panel.active { display: flex; }
.dash-topbar {
  padding: 12px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0; box-shadow: var(--shadow-xs);
}
.dash-title { font-family: 'Syne', sans-serif; font-size: 15px; font-weight: 800; color: var(--accent); }
.dash-sub { font-size: 10px; color: var(--muted); margin-top: 2px; }
.dash-controls { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.dash-select {
  background: var(--surface2); border: 1px solid var(--border);
  color: var(--text); padding: 5px 9px;
  border-radius: var(--radius-sm); font-family: 'DM Sans', sans-serif;
  font-size: 11px; outline: none; cursor: pointer;
}
.dash-body { flex: 1; overflow-y: auto; padding: 16px 20px 40px; }

/* ─── KPI CARDS ─────────────────────────── */
.dash-kpis { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 16px; }
.kpi-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 14px 15px;
  position: relative; overflow: hidden;
  cursor: pointer; transition: all 0.15s; box-shadow: var(--shadow-xs);
}
.kpi-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); border-color: var(--accent3); }
.kpi-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
}
.kpi-card:nth-child(1)::before { background: linear-gradient(90deg, var(--accent), var(--accent3)); }
.kpi-card:nth-child(2)::before { background: linear-gradient(90deg, #7ab800, var(--lime)); }
.kpi-card:nth-child(3)::before { background: linear-gradient(90deg, var(--gold), #f0a820); }
.kpi-card:nth-child(4)::before { background: linear-gradient(90deg, var(--green), #28b864); }
.kpi-card:nth-child(5)::before { background: linear-gradient(90deg, var(--purple), #8060c8); }
.kpi-label { font-size: 9px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 6px; font-weight: 700; }
.kpi-value { font-family: 'Syne', sans-serif; font-size: 28px; font-weight: 800; line-height: 1; }
.kpi-card:nth-child(1) .kpi-value { color: var(--accent); }
.kpi-card:nth-child(2) .kpi-value { color: #4a7000; }
.kpi-card:nth-child(3) .kpi-value { color: var(--gold); }
.kpi-card:nth-child(4) .kpi-value { color: var(--green); }
.kpi-card:nth-child(5) .kpi-value { color: var(--purple); }
.kpi-sub { font-size: 10px; color: var(--muted); margin-top: 4px; }
.kpi-trend {
  position: absolute; top: 12px; right: 12px;
  font-size: 10px; font-weight: 700;
  padding: 2px 7px; border-radius: 100px;
}
.kpi-trend.up { background: rgba(30,143,84,0.1); color: var(--green); }
.kpi-trend.down { background: rgba(200,57,43,0.08); color: var(--red); }

/* ─── CHART GRID ────────────────────────── */
.charts-grid { display: grid; grid-template-columns: repeat(2,1fr); gap: 12px; margin-bottom: 12px; }
.charts-grid.cols-1 { grid-template-columns: 1fr; }
.charts-grid.cols-3 { grid-template-columns: repeat(3,1fr); }
.chart-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: 15px 16px;
  position: relative; transition: all 0.15s; box-shadow: var(--shadow-xs);
}
.chart-card:hover { border-color: var(--accent3); box-shadow: var(--shadow); }
.chart-card.dragging { opacity: 0.4; border: 2px dashed var(--accent3); }
.chart-card.drag-over { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(26,60,46,0.12); }
.chart-card.span2 { grid-column: span 2; }
.chart-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.chart-drag-handle { cursor: grab; color: var(--border2); font-size: 14px; padding: 2px; flex-shrink: 0; }
.chart-drag-handle:hover { color: var(--muted); }
.chart-drag-handle:active { cursor: grabbing; }
.chart-title {
  font-family: 'Syne', sans-serif;
  font-size: 10px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.1em;
  color: var(--muted); flex: 1;
}
.chart-actions { display: flex; gap: 4px; margin-left: auto; opacity: 0; transition: opacity 0.15s; }
.chart-card:hover .chart-actions { opacity: 1; }
.chart-action-btn {
  background: none; border: 1px solid var(--border);
  color: var(--muted); border-radius: 5px;
  width: 22px; height: 22px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; transition: all 0.15s; padding: 0;
}
.chart-action-btn:hover { background: var(--surface2); color: var(--accent); }
.chart-badge {
  font-size: 9px; padding: 2px 7px; border-radius: 100px;
  background: rgba(26,60,46,0.07); color: var(--accent);
  font-weight: 700; flex-shrink: 0;
  border: 1px solid rgba(26,60,46,0.12);
}
.chart-wrap { position: relative; }
.chart-empty { font-size: 11px; color: var(--muted2); text-align: center; padding: 30px 0; }

.add-chart-btn {
  border: 2px dashed var(--border);
  border-radius: var(--radius-lg);
  padding: 18px; display: flex; align-items: center;
  justify-content: center; gap: 8px;
  cursor: pointer; color: var(--muted2);
  font-size: 12px; font-weight: 600;
  transition: all 0.15s; background: none; width: 100%;
  font-family: 'DM Sans', sans-serif;
}
.add-chart-btn:hover { border-color: var(--accent3); color: var(--accent); background: rgba(26,60,46,0.02); }

/* ─── CHART PICKER MODAL ────────────────── */
.chart-picker-overlay { position: fixed; inset: 0; background: rgba(17,26,20,0.55); z-index: 1000; display: none; align-items: center; justify-content: center; backdrop-filter: blur(2px); }
.chart-picker-overlay.open { display: flex; }
.chart-picker-modal {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-xl); width: 560px;
  max-height: 80vh; overflow: hidden;
  display: flex; flex-direction: column;
  box-shadow: var(--shadow-lg);
}
.chart-picker-header {
  padding: 16px 20px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  background: var(--surface2);
}
.chart-picker-title { font-family: 'Syne', sans-serif; font-size: 14px; font-weight: 800; color: var(--accent); }
.chart-picker-body { padding: 16px; overflow-y: auto; display: grid; grid-template-columns: repeat(3,1fr); gap: 10px; }
.chart-type-card {
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 14px; cursor: pointer; transition: all 0.15s;
  text-align: center; background: var(--surface);
}
.chart-type-card:hover { border-color: var(--accent); background: rgba(26,60,46,0.04); box-shadow: var(--shadow); }
.chart-type-icon { font-size: 22px; margin-bottom: 6px; }
.chart-type-name { font-size: 11px; font-weight: 700; color: var(--text); }
.chart-type-desc { font-size: 9px; color: var(--muted); margin-top: 3px; }

/* ─── DRILLDOWN MODAL ───────────────────── */
.drilldown-overlay { position: fixed; inset: 0; background: rgba(17,26,20,0.55); z-index: 1000; display: none; align-items: center; justify-content: center; backdrop-filter: blur(2px); }
.drilldown-overlay.open { display: flex; }
.drilldown-modal {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-xl); width: 700px;
  max-height: 85vh; overflow: hidden;
  display: flex; flex-direction: column;
  box-shadow: var(--shadow-lg);
}
.drilldown-header {
  padding: 14px 20px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  background: var(--surface2);
}
.drilldown-title { font-family: 'Syne', sans-serif; font-size: 14px; font-weight: 800; color: var(--accent); }
.drilldown-body { flex: 1; overflow-y: auto; padding: 16px 20px; }
.drilldown-table { width: 100%; border-collapse: collapse; font-size: 11px; }
.drilldown-table th {
  text-align: left; padding: 7px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 9px; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.1em;
  font-weight: 700; background: var(--surface2);
}
.drilldown-table td { padding: 7px 10px; border-bottom: 1px solid var(--border); color: var(--text); }
.drilldown-table tr:hover td { background: var(--surface2); }

/* ─── INSIGHT CARDS ─────────────────────── */
.insight-row { display: grid; grid-template-columns: repeat(3,1fr); gap: 12px; margin-bottom: 14px; }
.insight-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 13px;
  box-shadow: var(--shadow-xs);
}
.insight-title {
  font-family: 'Syne', sans-serif; font-size: 10px;
  font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.1em; color: var(--accent); margin-bottom: 8px;
}
.insight-list { display: flex; flex-direction: column; gap: 5px; }
.insight-item {
  display: flex; align-items: center; gap: 7px;
  font-size: 11px; cursor: pointer;
  border-radius: var(--radius-sm); padding: 2px 4px;
  transition: background 0.1s;
}
.insight-item:hover { background: var(--surface2); }
.insight-bar-wrap { flex: 1; height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; }
.insight-bar-fill { height: 100%; border-radius: 2px; }
.insight-name { width: 90px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--text2); }
.insight-count { font-size: 10px; color: var(--muted); width: 24px; text-align: right; flex-shrink: 0; }

/* ─── LAYOUT CONTROLS ───────────────────── */
.dash-layout-btns { display: flex; gap: 2px; background: var(--surface2); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 3px; }
.dash-layout-btn { background: none; border: none; color: var(--muted); cursor: pointer; padding: 3px 7px; border-radius: 4px; font-size: 11px; transition: all 0.15s; }
.dash-layout-btn.active { background: var(--surface); color: var(--accent); box-shadow: var(--shadow-xs); }

/* ─── DB PANEL ──────────────────────────── */
.db-panel { display: none; flex: 1; flex-direction: column; overflow: hidden; }
.db-panel.active { display: flex; }
.db-topbar {
  padding: 12px 20px; border-bottom: 1px solid var(--border);
  background: var(--surface);
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0; box-shadow: var(--shadow-xs);
}
.db-title { font-family: 'Syne', sans-serif; font-size: 15px; font-weight: 800; color: var(--accent); }
.db-sub { font-size: 11px; color: var(--muted); margin-top: 2px; }
.db-body { flex: 1; overflow-y: auto; padding: 16px 20px; }
.db-table-wrap { overflow-x: auto; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); box-shadow: var(--shadow-xs); }
.db-table { width: 100%; border-collapse: collapse; font-size: 11px; }
.db-table th { text-align: left; padding: 10px 14px; border-bottom: 1px solid var(--border); font-size: 9px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700; background: var(--surface2); white-space: nowrap; }
.db-table td { padding: 9px 14px; border-bottom: 1px solid var(--border); color: var(--text); vertical-align: top; }
.db-table tr:last-child td { border-bottom: none; }
.db-table tr:hover td { background: rgba(26,60,46,0.025); }
.db-badge { font-size: 9px; padding: 2px 8px; border-radius: 100px; font-weight: 700; background: rgba(26,60,46,0.07); color: var(--accent); border: 1px solid rgba(26,60,46,0.12); }

/* ─── COLLECT MODAL ─────────────────────── */
.modal-overlay { position: fixed; inset: 0; background: rgba(17,26,20,0.55); z-index: 1000; display: none; align-items: center; justify-content: center; backdrop-filter: blur(2px); }
.modal-overlay.open { display: flex; }
.modal {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-xl); width: 600px;
  max-height: 85vh; overflow: hidden;
  display: flex; flex-direction: column;
  box-shadow: 0 24px 70px rgba(17,26,20,0.22);
}
.modal-head { padding: 16px 20px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; background: var(--surface2); }
.modal-header { padding: 16px 20px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; background: var(--surface2); }
.modal-title { font-family: 'Syne', sans-serif; font-size: 14px; font-weight: 800; color: var(--accent); }
.modal-body { flex: 1; overflow-y: auto; padding: 16px 20px; }
.modal-footer { padding: 12px 20px; border-top: 1px solid var(--border); display: flex; gap: 8px; justify-content: flex-end; background: var(--surface2); }
.modal-url { font-size: 11px; color: var(--muted); word-break: break-all; padding: 8px 10px; background: var(--surface2); border-radius: var(--radius-sm); border: 1px solid var(--border); margin-bottom: 12px; }
.modal-status { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 30px 0; color: var(--muted); font-size: 12px; text-align: center; }
.field-group { margin-bottom: 12px; }
.field-label { font-size: 10px; color: var(--muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 5px; }
.field-val { font-size: 12px; color: var(--text); line-height: 1.5; padding: 8px 10px; background: var(--surface2); border-radius: var(--radius-sm); border: 1px solid var(--border); }
.field-val.empty { color: var(--muted2); font-style: italic; }
.close-btn { width: 28px; height: 28px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface); color: var(--muted); cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 14px; transition: all 0.15s; }
.close-btn:hover { background: var(--surface2); color: var(--accent); border-color: var(--accent3); }

/* ─── TOAST ─────────────────────────────── */
.toast {
  position: fixed; bottom: 20px; right: 20px;
  background: var(--accent);
  background-image: linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%);
  color: var(--lime); border-radius: var(--radius);
  padding: 10px 16px; font-size: 12px; font-weight: 700;
  z-index: 9999; opacity: 0; transition: all 0.25s;
  transform: translateY(10px);
  border: 1px solid rgba(200,232,78,0.25);
  box-shadow: var(--shadow-md);
  max-width: 320px;
}
.toast.show { opacity: 1; transform: translateY(0); }

/* ─── TAG PROGRESS ──────────────────────── */
.tag-progress { display: none; align-items: center; gap: 8px; font-size: 11px; padding: 5px 12px; background: rgba(26,60,46,0.07); border-radius: var(--radius-sm); border: 1px solid rgba(26,60,46,0.15); }
.tag-progress.active { display: flex; }
.tag-prog-bar { flex: 1; height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; max-width: 120px; }
.tag-prog-fill { height: 100%; background: var(--lime); border-radius: 2px; transition: width 0.3s; }

/* ─── VEILLE 360 PANEL ──────────────────── */
.v360-panel { display: none; flex: 1; flex-direction: column; overflow: hidden; }
.v360-panel.active { display: flex; }
.v360-topbar { padding: 14px 20px; border-bottom: 1px solid var(--border); background: var(--surface); display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
.v360-title { font-family: 'Syne', sans-serif; font-size: 15px; font-weight: 800; color: var(--accent); }
.v360-body { flex: 1; overflow-y: auto; padding: 20px; display: flex; gap: 20px; }
.v360-form-col { flex: 1; min-width: 300px; display: flex; flex-direction: column; gap: 14px; }
.v360-result-col { flex: 1.4; display: flex; flex-direction: column; gap: 12px; }
.v360-section { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 16px; box-shadow: var(--shadow-xs); }
.v360-section-title { font-family: 'Syne', sans-serif; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--accent); margin-bottom: 12px; }
.v360-textarea { width: 100%; background: var(--surface2); border: 1px solid var(--border); color: var(--text); padding: 10px; border-radius: var(--radius-sm); font-size: 12px; font-family: 'DM Sans', sans-serif; outline: none; resize: vertical; transition: all 0.15s; min-height: 100px; }
.v360-textarea:focus { border-color: var(--accent3); box-shadow: 0 0 0 2px rgba(26,60,46,0.07); }
.v360-file-drop { border: 2px dashed var(--border); border-radius: var(--radius); padding: 16px; text-align: center; cursor: pointer; transition: all 0.15s; color: var(--muted2); font-size: 11px; }
.v360-file-drop:hover { border-color: var(--accent3); color: var(--accent); background: rgba(26,60,46,0.02); }
.v360-file-list { font-size: 11px; color: var(--muted); margin-top: 8px; }
.v360-result-box { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 16px; flex: 1; overflow-y: auto; box-shadow: var(--shadow-xs); }
.v360-result-content { font-size: 12px; line-height: 1.65; color: var(--text2); white-space: pre-wrap; }
.v360-status { font-size: 11px; color: var(--muted); font-style: italic; }


/* ─── CARD NEW LAYOUT ───────────────────── */
.card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.card-img-wrap {
  flex-shrink: 0;
  width: 52px; height: 52px;
  border-radius: 10px;
  overflow: hidden;
  background: var(--surface3);
  border: 1px solid var(--border);
  display: flex; align-items: center; justify-content: center;
  margin-top: 2px;
}
.card-img {
  width: 100%; height: 100%;
  object-fit: cover;
}
.card-body { flex: 1; min-width: 0; }
.card-meta-row {
  display: flex; align-items: center; gap: 6px;
  font-size: 10px; color: var(--muted);
  flex-wrap: wrap; margin-bottom: 4px;
}
.card-source { font-weight: 700; color: var(--accent3); }
.card-date { margin-left: auto; color: var(--muted2); white-space: nowrap; }
.card-title-green {
  font-size: 13px; font-weight: 700; line-height: 1.38;
  color: var(--accent); margin-bottom: 4px;
}
.card-title-green a {
  color: var(--accent);
  text-decoration: none;
}
.card-title-green a:hover {
  color: var(--accent2);
  text-decoration: underline;
  text-decoration-color: var(--lime2);
}

/* ─── SIDEBAR DRAG & DROP ───────────────── */
.nav-all-row {
  display: flex; align-items: center;
  padding: 4px 8px 2px;
  gap: 4px;
}
.nav-all-row .nav-all { flex: 1; }
.nav-add-folder-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px;
  background: none;
  border: 1.5px dashed var(--border);
  border-radius: var(--radius-sm);
  font-size: 14px; cursor: pointer;
  color: var(--muted2);
  transition: all 0.15s; flex-shrink: 0;
  opacity: 0.55;
  position: relative;
}
.nav-add-folder-btn:hover {
  opacity: 1;
  border-color: var(--accent3);
  background: var(--lime-bg);
  color: var(--accent);
  border-style: solid;
}
.nav-add-folder-btn::after {
  content: '+';
  position: absolute;
  bottom: -3px; right: -3px;
  width: 11px; height: 11px;
  background: var(--accent);
  color: var(--lime);
  border-radius: 50%;
  font-size: 9px; font-weight: 900;
  display: flex; align-items: center; justify-content: center;
  line-height: 11px; text-align: center;
}
.nav-cat-header { cursor: grab; user-select: none; }
.nav-cat-header:active { cursor: grabbing; }
.nav-cat.drag-over > .nav-cat-header {
  background: var(--lime-bg);
  border-color: var(--lime2);
}
.nav-cat.dragging { opacity: 0.45; }
.nav-cat-header .drag-handle {
  color: var(--border2);
  font-size: 11px;
  margin-right: 2px;
  cursor: grab;
}

/* ─── SIDEBAR CONTEXT MENU ──────────────── */
.nav-ctx-menu {
  position: fixed;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  min-width: 180px;
  z-index: 9999;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}
.nav-ctx-item {
  padding: 9px 14px;
  font-size: 11px;
  cursor: pointer;
  color: var(--text);
  display: flex; align-items: center; gap: 8px;
  transition: background 0.1s;
  font-weight: 500;
}
.nav-ctx-item:hover { background: var(--surface2); color: var(--accent); }
.nav-ctx-item.danger:hover { background: rgba(200,57,43,0.06); color: var(--red); }
.nav-ctx-sep { height: 1px; background: var(--border); }


/* ─── SOURCE ORGANIZATION PANEL ─────────────────── */
.add-form-title {
  font-family: 'Syne', sans-serif;
  font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--muted); margin-bottom: 12px;
}
.src-folder {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  margin-bottom: 8px;
  background: var(--surface);
  overflow: hidden;
}
.src-folder-header {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  background: var(--surface2);
  border-bottom: 1px solid var(--border);
  user-select: none;
  transition: background 0.15s;
}
.src-folder-header:hover { background: var(--surface3); }
.src-folder-arrow { font-size: 9px; color: var(--muted); width: 10px; }
.src-folder-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.src-folder-name { font-size: 12px; font-weight: 700; color: var(--accent); flex: 1; font-family: 'Syne', sans-serif; }
.src-folder-count { font-size: 10px; background: var(--accent); color: white; border-radius: 10px; padding: 1px 7px; }
.src-folder-body { display: none; }
.src-folder-body.open { display: block; }

.src-subfolder { border-top: 1px solid var(--border); }
.src-subfolder-header {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 14px 6px 24px;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
}
.src-subfolder-name { font-size: 11px; font-weight: 600; color: var(--text); flex: 1; }
.src-subfolder-count { font-size: 10px; color: var(--muted); }
.src-subfolder-body { padding: 4px 0; }

.src-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 14px 8px 32px;
  border-bottom: 1px solid var(--border);
  transition: background 0.1s;
  cursor: default;
}
.src-row:last-child { border-bottom: none; }
.src-row:hover { background: var(--surface2); }
.src-row.dragging { opacity: 0.45; }
.src-row.drag-over { background: var(--lime-bg); border-top: 2px solid var(--lime2); }

.src-row-drag {
  color: var(--border2); font-size: 14px; cursor: grab;
  flex-shrink: 0; opacity: 0.5;
  transition: opacity 0.15s;
}
.src-row:hover .src-row-drag { opacity: 1; }
.src-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.src-info { flex: 1; min-width: 0; }
.src-name { font-size: 11px; font-weight: 600; color: var(--text); }
.src-url { font-size: 10px; color: var(--muted); text-decoration: none; display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.src-url:hover { color: var(--accent3); text-decoration: underline; }
.src-row-badges { display: flex; gap: 4px; flex-shrink: 0; }
.src-cat-badge { font-size: 9px; background: var(--surface3); color: var(--muted); border-radius: 4px; padding: 2px 6px; font-weight: 600; }
.src-region-badge { font-size: 9px; background: var(--lime-bg); color: var(--accent); border-radius: 4px; padding: 2px 6px; font-weight: 600; }
.src-badge { font-size: 9px; border-radius: 4px; padding: 2px 6px; font-weight: 700; }
.src-badge.static { background: rgba(100,180,120,0.12); color: #3a8a4e; }
.src-badge.dynamic { background: rgba(80,120,220,0.1); color: #4a5eac; }
.src-row-actions { display: flex; gap: 4px; flex-shrink: 0; }
.src-move-btn {
  background: none; border: 1px solid var(--border);
  color: var(--muted); font-size: 11px;
  border-radius: var(--radius-sm); padding: 2px 6px;
  cursor: pointer; transition: all 0.15s;
}
.src-move-btn:hover { background: var(--accent); color: white; border-color: var(--accent); }
.btn-del {
  background: none; border: 1px solid rgba(200,57,43,0.2);
  color: var(--red, #c8392b); font-size: 11px;
  border-radius: var(--radius-sm); padding: 2px 7px;
  cursor: pointer; transition: all 0.15s;
}
.btn-del:hover { background: rgba(200,57,43,0.08); }

/* Source view toggle */
.src-view-toggle { display: flex; gap: 2px; }
.src-view-btn {
  font-size: 10px; padding: 4px 10px;
  border: 1px solid var(--border);
  background: var(--surface2); color: var(--muted);
  border-radius: var(--radius-sm); cursor: pointer;
  font-weight: 600; transition: all 0.15s;
}
.src-view-btn.active { background: var(--accent); color: white; border-color: var(--accent); }

/* ─── NAV DRAG HANDLES ───────────────────── */
.nav-drag-handle {
  color: var(--border2); font-size: 13px; cursor: grab;
  opacity: 0; transition: opacity 0.15s;
  flex-shrink: 0;
}
.nav-cat-header:hover .nav-drag-handle { opacity: 0.7; }
.nav-cat-header:active .nav-drag-handle { cursor: grabbing; }

.nav-region-drag {
  color: var(--border2); font-size: 11px; cursor: grab;
  opacity: 0; transition: opacity 0.15s;
  flex-shrink: 0;
}
.nav-region:hover .nav-region-drag { opacity: 0.7; }

.nav-cat.dragging { opacity: 0.45; }
.nav-cat.drag-over > .nav-cat-header {
  background: var(--lime-bg);
  outline: 2px solid var(--lime2);
  border-radius: var(--radius-sm);
}
.nav-region.dragging { opacity: 0.45; }
.nav-region.drag-over { background: var(--lime-bg); border-radius: var(--radius-sm); }

/* ─── NAV CONTEXT MENU ───────────────────── */
.nav-ctx-menu {
  position: fixed;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  min-width: 190px;
  z-index: 9999;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}
.nav-ctx-item {
  padding: 9px 14px;
  font-size: 11px;
  cursor: pointer;
  color: var(--text);
  display: flex; align-items: center; gap: 8px;
  transition: background 0.1s;
  font-weight: 500;
}
.nav-ctx-item:hover { background: var(--surface2); color: var(--accent); }
.nav-ctx-item.danger:hover { background: rgba(200,57,43,0.06); color: var(--red, #c8392b); }
.nav-ctx-sep { height: 1px; background: var(--border); margin: 2px 0; }

/* ─── SOURCE MOVE MODAL ──────────────────── */
.modal-title { font-family: 'Syne', sans-serif; font-size: 15px; font-weight: 800; color: var(--accent); padding: 16px 20px 0; }
.modal-body { padding: 14px 20px; }
.modal-footer { padding: 12px 20px; border-top: 1px solid var(--border); display: flex; gap: 8px; justify-content: flex-end; }

/* ─── SCROLLBARS ────────────────────────── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--muted2); }

</style>

<script>
// -- NanoChart - Canvas renderer natif, sans CDN -----------------------------
const NanoChart = (() => {
  const PR = window.devicePixelRatio || 1;
  function setup(canvas) {
    const W = canvas.clientWidth || canvas.parentElement.clientWidth || 400;
    const H = canvas.clientHeight || 200;
    canvas.width = W * PR; canvas.height = H * PR;
    canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(PR, PR);
    return { ctx, W, H };
  }
  function hexA(hex, a) {
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    return `rgba(${r},${g},${b},${a})`;
  }
  function drawGrid(ctx, W, H, pad, maxV, steps=4) {
    ctx.strokeStyle = 'rgba(0,0,0,0.07)'; ctx.lineWidth = 0.5;
    for (let i = 0; i <= steps; i++) {
      const y = pad.top + (H - pad.top - pad.bottom) * (1 - i/steps);
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
      const v = Math.round(maxV * i / steps);
      ctx.fillStyle = '#9aa59a'; ctx.font = `${9*PR/PR}px sans-serif`; ctx.textAlign = 'right';
      ctx.fillText(v, pad.left - 4, y + 3);
    }
  }

  // Bar chart (horizontal or vertical)
  function bar(canvas, labels, values, colors, opts={}) {
    if (!canvas) return;
    const { ctx, W, H } = setup(canvas);
    const horiz = opts.horizontal || false;
    const maxV = Math.max(...values, 1);
    const pad = horiz ? {top:4, bottom:4, left: Math.min(120, W*0.35), right:40}
                      : {top:20, bottom:32, left:32, right:8};
    const n = values.length;
    ctx.clearRect(0, 0, W, H);

    if (!horiz) {
      drawGrid(ctx, W, H, pad, maxV);
      const bw = Math.max(4, (W - pad.left - pad.right) / n - 4);
      values.forEach((v, i) => {
        const bh = ((v / maxV) * (H - pad.top - pad.bottom));
        const x = pad.left + i * ((W - pad.left - pad.right) / n) + 2;
        const y = H - pad.bottom - bh;
        const col = Array.isArray(colors) ? colors[i % colors.length] : (colors || '#1a3c2e');
        ctx.fillStyle = typeof col === 'string' && col.startsWith('#') ? hexA(col, 0.85) : col;
        const r = Math.min(4, bw/4);
        ctx.beginPath();
        ctx.moveTo(x+r, y); ctx.lineTo(x+bw-r, y);
        ctx.quadraticCurveTo(x+bw, y, x+bw, y+r);
        ctx.lineTo(x+bw, y+bh); ctx.lineTo(x, y+bh);
        ctx.lineTo(x, y+r); ctx.quadraticCurveTo(x, y, x+r, y);
        ctx.closePath(); ctx.fill();
        // label
        const lbl = String(labels[i] || '').slice(0, 8);
        ctx.fillStyle = '#6b7a6b'; ctx.font = `9px sans-serif`; ctx.textAlign = 'center';
        ctx.fillText(lbl, x + bw/2, H - pad.bottom + 12);
        // value on hover area (tooltip via title)
      });
      // onclick support
      canvas._barData = { labels, values, horizontal: false, pad, W, H, bw: (W - pad.left - pad.right) / n };
    } else {
      const bh = Math.max(4, (H - pad.top - pad.bottom) / n - 4);
      values.forEach((v, i) => {
        const bw2 = Math.max(1, (v / maxV) * (W - pad.left - pad.right));
        const y = pad.top + i * ((H - pad.top - pad.bottom) / n) + 2;
        const col = Array.isArray(colors) ? colors[i % colors.length] : (colors || '#1a3c2e');
        ctx.fillStyle = typeof col === 'string' && col.startsWith('#') ? hexA(col, 0.85) : col;
        const r = Math.min(4, bh/4);
        ctx.beginPath();
        ctx.moveTo(pad.left, y+r); ctx.lineTo(pad.left, y+bh-r);
        ctx.quadraticCurveTo(pad.left, y+bh, pad.left+r, y+bh);
        ctx.lineTo(pad.left+bw2-r, y+bh);
        ctx.quadraticCurveTo(pad.left+bw2, y+bh, pad.left+bw2, y+bh-r);
        ctx.lineTo(pad.left+bw2, y+r);
        ctx.quadraticCurveTo(pad.left+bw2, y, pad.left+bw2-r, y);
        ctx.lineTo(pad.left+r, y); ctx.quadraticCurveTo(pad.left, y, pad.left, y+r);
        ctx.closePath(); ctx.fill();
        // label
        const lbl = String(labels[i] || '').slice(0, 20);
        ctx.fillStyle = '#3a4a3a'; ctx.font = `9px sans-serif`; ctx.textAlign = 'right';
        ctx.fillText(lbl, pad.left - 4, y + bh/2 + 3);
        // value
        ctx.fillStyle = '#6b7a6b'; ctx.textAlign = 'left';
        ctx.fillText(v, pad.left + bw2 + 4, y + bh/2 + 3);
      });
      canvas._barData = { labels, values, horizontal: true, pad, W, H, bh: (H - pad.top - pad.bottom) / n };
    }
    // Simple click handler
    canvas.onclick = function(e) {
      const d = canvas._barData; if (!d || !canvas._onClick) return;
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      if (!d.horizontal) {
        const idx = Math.floor((mx - d.pad.left) / d.bw);
        if (idx >= 0 && idx < d.labels.length) canvas._onClick(idx, d.labels[idx], d.values[idx]);
      } else {
        const idx = Math.floor((my - d.pad.top) / d.bh);
        if (idx >= 0 && idx < d.labels.length) canvas._onClick(idx, d.labels[idx], d.values[idx]);
      }
    };
  }

  // Line chart
  function line(canvas, labels, datasets, opts={}) {
    if (!canvas) return;
    const { ctx, W, H } = setup(canvas);
    const allVals = datasets.flatMap(d => d.data.map(Number)).filter(isFinite);
    const maxV = Math.max(...allVals, 1);
    const minV = opts.minY !== undefined ? opts.minY : Math.min(...allVals, 0);
    const pad = {top:20, bottom:28, left:36, right:8};
    const range = maxV - minV || 1;
    const n = labels.length;
    ctx.clearRect(0, 0, W, H);
    drawGrid(ctx, W, H, pad, maxV);
    datasets.forEach(ds => {
      const pts = ds.data.map((v,i) => ({
        x: pad.left + i/(n-1||1) * (W-pad.left-pad.right),
        y: H - pad.bottom - ((Number(v)-minV)/range) * (H-pad.top-pad.bottom)
      }));
      // Fill
      if (ds.fill) {
        ctx.beginPath();
        ctx.moveTo(pts[0].x, H - pad.bottom);
        pts.forEach(p => ctx.lineTo(p.x, p.y));
        ctx.lineTo(pts[pts.length-1].x, H - pad.bottom);
        ctx.closePath();
        ctx.fillStyle = ds.fillColor || 'rgba(59,130,246,0.08)';
        ctx.fill();
      }
      // Line
      ctx.beginPath();
      pts.forEach((p,i) => {
        if (i===0) ctx.moveTo(p.x, p.y);
        else {
          const prev = pts[i-1];
          const cx = (prev.x + p.x) / 2;
          ctx.bezierCurveTo(cx, prev.y, cx, p.y, p.x, p.y);
        }
      });
      ctx.strokeStyle = ds.color || '#3b82f6';
      ctx.lineWidth = 2;
      ctx.stroke();
      // Dots
      pts.forEach(p => {
        ctx.beginPath(); ctx.arc(p.x, p.y, 2.5, 0, Math.PI*2);
        ctx.fillStyle = ds.color || '#3b82f6'; ctx.fill();
      });
    });
    // x labels (sparse)
    const step = Math.ceil(n / 10);
    labels.forEach((l,i) => {
      if (i % step !== 0) return;
      const x = pad.left + i/(n-1||1) * (W-pad.left-pad.right);
      ctx.fillStyle = '#9aa59a'; ctx.font = '9px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText(String(l).slice(0,5), x, H - pad.bottom + 12);
    });
  }

  // Doughnut chart
  function doughnut(canvas, labels, values, colors, opts={}) {
    if (!canvas) return;
    const { ctx, W, H } = setup(canvas);
    const total = values.reduce((a,b) => a+b, 0) || 1;
    const cx = W/2, cy = H/2 - 10;
    const r = Math.min(cx, cy) * 0.72;
    const inner = r * 0.58;
    ctx.clearRect(0, 0, W, H);
    let angle = -Math.PI/2;
    values.forEach((v, i) => {
      const slice = (v / total) * Math.PI * 2;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, r, angle, angle + slice);
      ctx.closePath();
      const col = colors[i % colors.length] || '#ccc';
      ctx.fillStyle = col.length === 9 ? col : (col + 'cc');
      ctx.fill();
      angle += slice;
    });
    // Hole
    ctx.beginPath(); ctx.arc(cx, cy, inner, 0, Math.PI*2);
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--surface') || '#fff';
    ctx.fill();
    // Total label
    ctx.fillStyle = '#1a3c2e'; ctx.font = `bold ${Math.round(r*0.28)}px sans-serif`; ctx.textAlign = 'center';
    ctx.fillText(total, cx, cy + 4);
    ctx.fillStyle = '#6b7a6b'; ctx.font = `${Math.round(r*0.16)}px sans-serif`;
    ctx.fillText('articles', cx, cy + r*0.22);
    // Legend
    const lh = 14, startY = H - (labels.length * lh) + 4;
    labels.forEach((l, i) => {
      if (!values[i]) return;
      const ly = startY + i * lh;
      ctx.fillStyle = colors[i % colors.length] || '#ccc';
      ctx.fillRect(8, ly, 10, 10);
      ctx.fillStyle = '#6b7a6b'; ctx.font = '9px sans-serif'; ctx.textAlign = 'left';
      ctx.fillText(`${l}: ${values[i]}`, 22, ly + 9);
    });
  }

  // Polar area (simplified as pie)
  function polar(canvas, labels, values, colors) {
    if (!canvas) return;
    doughnut(canvas, labels, values, colors, { cutout: 0 });
    // Re-draw without hole
    const { ctx, W, H } = setup(canvas);
    const total = values.reduce((a,b) => a+b, 0) || 1;
    const cx = W/2, cy = H/2 - 8;
    const r = Math.min(cx, cy) * 0.7;
    ctx.clearRect(0, 0, W, H);
    let angle = -Math.PI/2;
    values.forEach((v, i) => {
      const slice = (v / total) * Math.PI * 2;
      ctx.beginPath(); ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, r, angle, angle + slice);
      ctx.closePath();
      ctx.fillStyle = (colors[i % colors.length] || '#ccc');
      ctx.fill();
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 1; ctx.stroke();
      angle += slice;
    });
    const lh = 13, startY = H - labels.length * lh + 2;
    labels.forEach((l, i) => {
      if (!values[i]) return;
      const ly = startY + i * lh;
      ctx.fillStyle = colors[i % colors.length] || '#ccc';
      ctx.fillRect(8, ly, 9, 9);
      ctx.fillStyle = '#6b7a6b'; ctx.font = '9px sans-serif'; ctx.textAlign = 'left';
      ctx.fillText(`${l.slice(0,18)}: ${values[i]}`, 21, ly + 8);
    });
  }

  return { bar, line, doughnut, polar };
})();
</script>
</head>
<body>

<!-- TITLEBAR -->
<div class="titlebar">
  <div class="logo">Substan<em>Ciel</em></div>
  <div class="live-badge"><div class="live-dot"></div>Live Scraping</div>
  <div class="titlebar-stats">
    <div class="ts-item"><span class="ts-val ts-accent" id="ts-total">—</span> <span>articles</span></div>
    <div class="ts-divider"></div>
    <div class="ts-item"><span class="ts-val" id="ts-today">—</span> <span>aujourd'hui</span></div>
    <div class="ts-divider"></div>
    <div class="ts-item"><span>Scrape toutes les</span> <span class="ts-val">6h</span></div>
  </div>
  <button class="scrape-btn" onclick="triggerScrape()">&#8959; Scraper</button>
  <button class="scrape-btn" id="btn-autotag" onclick="openAutoTagPanel()" style="background:var(--lime);color:var(--accent);font-size:11px" title="Agent IA de curation automatique">🤖 Curation IA</button>
</div>
<div class="tabs-bar">
  <button class="tab-btn active" id="tab-feed" onclick="switchTab('feed')">Veille</button>
  <button class="tab-btn" id="tab-sources" onclick="switchTab('sources')">Sources</button>
  <button class="tab-btn" id="tab-dashboard" onclick="switchTab('dashboard')">Dashboard</button>
  <button class="tab-btn" id="tab-360" onclick="switchTab('360')">Veille 360°</button>
  <button class="tab-btn" id="tab-pdf" onclick="switchTab('pdf')">📋 Cahiers des charges</button>
  <a class="tab-btn" href="/consultant" style="margin-left:auto;background:var(--lime);color:var(--accent);font-weight:700;text-decoration:none;display:inline-flex;align-items:center;gap:5px">📥 Espace collecte ↗</a>
</div>

<div class="app">

  <!-- SIDEBAR -->
  <aside class="sidebar">
    <div class="sidebar-top">
      <div class="sidebar-search">
        <span class="sidebar-search-icon">🔍</span>
        <input type="text" id="nav-search" placeholder="Filtrer les sources…" oninput="filterNav(this.value)" />
      </div>
      <div class="sidebar-actions">
        <button class="sidebar-action-btn" onclick="collapseAll()" title="Tout replier">⊖ Replier</button>
        <button class="sidebar-action-btn" onclick="expandAll()" title="Tout déplier">⊕ Déplier</button>
      </div>
    </div>

    <div class="nav-scroll" id="nav-scroll">
      <!-- Nav built by JS -->
    </div>

    <div class="sidebar-bottom">
      <div class="mini-stat" title="Nombre de sources qui ont bien répondu lors du dernier scraping"><span class="mini-label">Sources OK</span><span class="mini-value" id="s-ok" style="color:var(--green)">—</span></div>
      <div class="mini-stat" title="Sources ayant retourné une erreur lors du dernier scraping (timeout, URL invalide…)"><span class="mini-label">Erreurs</span><span class="mini-value" id="s-err" style="color:var(--red)">—</span></div>
      <div class="mini-stat"><span class="mini-label">Dernier scrape</span><span class="mini-value" id="s-last" style="color:var(--gold);font-size:10px">—</span></div>
    </div>
  </aside>

  <!-- MAIN -->
  <div class="main">
    <div class="toolbar">
      <div class="search-wrap">
        <span class="search-icon">🔍</span>
        <input type="text" id="search" placeholder="Rechercher titre, source, région…" oninput="onSearch()" />
      </div>
      <span class="spin" id="spin" style="font-size:16px;color:var(--muted);display:none;animation:spin 1s linear infinite">↻</span>
    </div>

    <div class="stats-row">
      <div class="stat-box"><div class="stat-lbl">Total</div><div class="stat-val" id="st-total">—</div></div>
      <div class="stat-box"><div class="stat-lbl">Aujourd'hui</div><div class="stat-val" id="st-today">—</div></div>
      <div class="stat-box" title="Sources ayant répondu correctement lors du dernier scraping"><div class="stat-lbl">Sources OK</div><div class="stat-val" id="st-ok2">—</div></div>
      <div class="stat-box"><div class="stat-lbl">Sources total</div><div class="stat-val" id="st-src">—</div></div>
      <div class="stat-box" title="Sources en erreur : timeout, URL invalide ou site inaccessible"><div class="stat-lbl">Erreurs</div><div class="stat-val" id="st-err">—</div></div>
    </div>
    
    <div class="toolbar-sel" id="sel-toolbar">
      <!-- Sélection -->
      <button class="sel-toggle-btn" id="btn-sel-toggle" onclick="toggleSelectAll()">
        <span id="sel-toggle-icon">☐</span> Tout
      </button>
      <span class="sel-count-badge" id="sel-count-wrap" style="display:none">
        <strong id="sel-count">0</strong> sél.
      </span>

      <div class="sel-divider"></div>

      <!-- Filtres dropdown -->
      <div class="sel-dropdown-wrap" id="filter-dropdown-wrap">
        <button class="sel-filter-btn" id="btn-filter-drop" onclick="toggleFilterDrop()">
          Filtres <span id="filter-active-dot" style="display:none;width:6px;height:6px;border-radius:50%;background:var(--lime);display:inline-block;margin-left:3px;vertical-align:middle"></span> ▾
        </button>
        <div class="sel-dropdown" id="filter-dropdown">
          <div class="sel-drop-item" id="drop-tagged" onclick="toggleTaggedOnly()">
            <span class="sel-drop-check" id="check-tagged">○</span> ⭐ Taggerés uniquement
          </div>
          <div class="sel-drop-item" id="drop-cdc" onclick="toggleCDCFilter()">
            <span class="sel-drop-check" id="check-cdc">○</span> 📋 CDC trouvé uniquement
          </div>
        </div>
      </div>

      <div style="flex:1"></div>

      <!-- Actions (visibles quand sélection > 0) -->
      <button class="btn-tag-sel" id="btn-tag" onclick="tagSelected()" disabled title="Tagger via IA">
        🏷 Tagger
      </button>

    </div>
    <div class="tag-progress" id="tag-progress">
      <span id="tag-prog-text">Tagging en cours…</span>
      <div class="tag-prog-bar"><div class="tag-prog-fill" id="tag-prog-fill" style="width:0%"></div></div>
      <span id="tag-prog-pct">0%</span>
    </div>

    <div class="progress"><div class="progress-fill" id="progress"></div></div>

    
    <div class="tag-bar-wrapper" id="tag-bar-wrapper">
      <div class="tag-bar-header">
        <button class="tag-bar-toggle" id="tag-bar-toggle" onclick="toggleTagBar()" title="Afficher/Masquer les tags">▼</button>
        <span class="tag-bar-label">Tags</span>
        
      </div>
      <div class="tag-bar" id="tag-bar" style="display:none"><!-- filled by JS --></div>
    </div>

    <div class="feed-area">
      <div class="feed-header">
        <span class="feed-title" id="feed-title">📰 Flux d'actualités</span>
        <span class="feed-meta" id="feed-meta"></span>
      </div>
      <div class="feed" id="feed">
        <div class="state-box"><div class="spinner"></div><p>Chargement…</p></div>
      </div>
    </div>
  </div>

  <!-- SOURCES PANEL -->
  <div class="src-panel" id="panel-sources">
    <div class="src-topbar">
      <div>
        <div class="src-title">Sources de veille</div>
        <div class="src-sub">Gérez les sites surveillés — ajoutez ou supprimez des sources</div>
      </div>
      <button class="btn btn-primary" onclick="triggerScrape()" style="font-size:11px;padding:8px 14px;">↻ Scraper maintenant</button>
    </div>
    <div class="src-body">
      <div class="add-form">
        <div class="add-form-title">Ajouter une source</div>
        <div class="form-row">
          <div class="form-field">
            <label class="form-label">Nom de la source</label>
            <input class="f-input" id="new-name" placeholder="Ex: Région Bretagne" />
          </div>
          <div class="form-field">
            <label class="form-label">Dossier <span style="font-size:9px;color:var(--muted)">(catégorie)</span></label>
            <select class="f-input" id="new-cat" onchange="onNewCatChange(this)">
              <option>Régions</option><option>Europe en Régions</option>
              <option>Opérateur national</option><option>Départements</option>
              <option>CRESS</option><option value="__new__">+ Nouveau dossier…</option>
            </select>
            <input class="f-input" id="new-custom-cat" placeholder="Nom du nouveau dossier" style="display:none;margin-top:4px" />
          </div>
          <div class="form-field">
            <label class="form-label">Sous-dossier <span style="font-size:9px;color:var(--muted)">(optionnel)</span></label>
            <input class="f-input" id="new-region" placeholder="Ex: Bretagne — laisser vide si aucun" />
          </div>
          <div class="form-field">
            <label class="form-label">URL</label>
            <input class="f-input" id="new-url" type="url" placeholder="https://..." />
          </div>
        </div>
        <div style="display:flex;gap:8px;margin-top:12px;align-items:center">
          <button class="btn btn-primary" onclick="addSource()">➕ Ajouter la source</button>
          <span style="font-size:10px;color:var(--muted)">Dossier inexistant ? <button onclick="createFolderFromPanel()" style="background:none;border:none;color:var(--accent3);font-size:10px;cursor:pointer;font-weight:700;padding:0;text-decoration:underline;font-family:inherit;">Créer d'abord le dossier →</button></span>
        </div>
        <p style="font-size:10px;color:var(--muted2);margin:6px 0 0;line-height:1.5">Le <strong style="color:var(--muted)">sous-dossier</strong> est optionnel — il permet de grouper au sein d'un même dossier (ex: "Régions" → "Bretagne")</p>
      </div>
      <div class="src-toolbar">
        <div class="src-search"><input placeholder="Filtrer les sources…" oninput="filterSources(this.value)" /></div>
        <span class="src-count" id="src-count">— sources</span>
        <div class="src-view-toggle">
          <button class="src-view-btn active" id="view-org" onclick="setSrcView('org')">Organisation</button>
          <button class="src-view-btn" id="view-list" onclick="setSrcView('list')">Liste</button>
        </div>
      </div>
      <div class="src-list" id="src-list"><div class="state-box"><div class="spinner"></div></div></div>
    </div>
  </div>

  <!-- DASHBOARD PANEL -->
  <div class="dash-panel" id="panel-dashboard">
    <div class="dash-topbar">
      <div>
        <div class="dash-title">Tableau de bord</div>
        <div class="dash-sub">Analyse sémantique et statistique — glissez les graphiques pour réorganiser</div>
      </div>
      <div class="dash-controls">
        <select class="dash-select" id="dash-period" onchange="loadDashboard()">
          <option value="7">7 derniers jours</option>
          <option value="30" selected>30 derniers jours</option>
          <option value="90">3 derniers mois</option>
          <option value="365">12 derniers mois</option>
          <option value="0">Tout</option>
        </select>
        <div class="dash-layout-btns">
          <button class="dash-layout-btn active" id="layout-2" onclick="setDashLayout(2)" title="2 colonnes">⬜⬜</button>
          <button class="dash-layout-btn" id="layout-1" onclick="setDashLayout(1)" title="1 colonne">⬜</button>
          <button class="dash-layout-btn" id="layout-3" onclick="setDashLayout(3)" title="3 colonnes">⬜⬜⬜</button>
        </div>
        <button class="btn" onclick="exportDashboardPNG()" style="font-size:11px;padding:6px 12px;" title="Exporter en PNG">📷 Export</button>
        <button class="btn btn-primary" onclick="loadDashboard()" style="font-size:11px;padding:6px 12px;">↻ Rafraîchir</button>
      </div>
    </div>
    <div class="dash-body" id="dash-body">
      <div class="state-box"><div class="spinner"></div><p>Chargement du dashboard…</p></div>
    </div>
  </div>

  <!-- DATABASE PANEL -->
  

  <!-- PANEL 360 -->
  <div class="src-panel" id="panel-pdf">
    <div class="src-topbar">
      <div>
        <div class="src-title">📋 Cahiers des charges</div>
        <div class="src-sub">CDC manquants sur tous les articles de la base</div>
      </div>
      <button class="btn btn-primary" onclick="cdcScanAll()" id="btn-pdf-scan-all" style="font-size:12px;padding:8px 18px;">
        🔍 Rechercher tous les CDC manquants
      </button>
    </div>
    <div style="flex:1;overflow-y:auto;padding:16px 20px;display:flex;flex-direction:column;gap:10px;">
      <div style="background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:14px;font-size:13px;color:var(--text2);line-height:1.6;">
        <strong style="color:var(--accent);">Comment ça marche ?</strong><br>
        Lance un scan sur <strong>tous les articles</strong> qui n’ont pas encore de CDC détecté.
        Le scraper cherche les liens PDF dans la page de chaque article et enregistre l’URL du CDC trouvé.
        Les CDC sont normalement détectés automatiquement au scraping &mdash; ce bouton permet de rattraper les oublis.
      </div>
      <div id="cdc-status" style="color:var(--text2);font-size:13px;padding:0 4px"></div>
      <div id="cdc-results-list" style="display:flex;flex-direction:column;gap:8px"></div>
    </div>
  </div>
<div class="src-panel" id="panel-360">
    <div class="src-topbar">
      <span style="font-size:15px;font-weight:800;">🔍 Veille 360° — Ingénierie financière CAPEX</span>
    </div>
    <div style="flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:16px;">
      <div style="background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:16px;">
        <div style="font-size:11px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px;">Description du projet</div>
        <textarea id="v360-project" placeholder="Décrivez votre projet d'investissement CAPEX : type de porteur (collectivité, entreprise...), nature des travaux, localisation, montant estimé, contexte..." style="width:100%;min-height:120px;background:var(--surface);border:1px solid var(--border);border-radius:8px;color:var(--text);padding:10px;font-size:12px;resize:vertical;font-family:inherit;box-sizing:border-box;"></textarea>
      </div>
      <div style="background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:16px;">
        <div style="font-size:11px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px;">Documents complémentaires (optionnel)</div>
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
          <label style="cursor:pointer;display:flex;align-items:center;gap:6px;padding:8px 14px;background:var(--surface);border:1px dashed var(--border);border-radius:8px;font-size:11px;color:var(--muted);transition:all 0.15s;" onmouseover="this.style.borderColor='var(--accent2)'" onmouseout="this.style.borderColor='var(--border)'">
            <input type="file" id="v360-files" multiple accept=".pdf,.txt,.docx" style="display:none" onchange="updateFileList()">
            📎 Ajouter des fichiers (PDF, TXT, DOCX)
          </label>
          <div id="v360-file-list" style="font-size:11px;color:var(--muted);"></div>
        </div>
      </div>
      <div style="display:flex;gap:10px;align-items:center;">
        <button class="btn btn-primary" onclick="runVeille360()" id="v360-btn" style="padding:10px 24px;font-size:13px;">
          🔍 Lancer la pré-analyse 360°
        </button>
        <button class="btn" onclick="clearVeille360()" style="font-size:11px;padding:8px 14px;">✕ Réinitialiser</button>
        <span id="v360-status" style="font-size:11px;color:var(--muted);"></span>
      </div>
      <div id="v360-result" style="display:none;"></div>
    </div>
  </div>

  <!-- COLLECT MODAL -->
  <div class="modal-overlay" id="collect-modal" onclick="if(event.target===this)closeModal()">
    <div class="modal">
      <div class="modal-head">
        <div class="modal-title" id="modal-title">📥 Collecte du dispositif</div>
        <button class="modal-close" onclick="closeModal()">✕</button>
      </div>
      <div class="modal-body" id="modal-body"><div class="modal-status"><div class="spinner"></div><p>Analyse en cours…</p></div></div>
      <div class="modal-footer" id="modal-footer" style="display:none;">
        <button class="btn" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);font-size:11px;padding:7px 14px;" onclick="closeModal()">Fermer</button>
        <button class="btn btn-primary" id="btn-save-collect" style="font-size:11px;padding:7px 14px;" onclick="saveCollect()">💾 Enregistrer</button>
      </div>
    </div>
  </div>

</div>

<script>

window.onerror = function(msg, src, line, col, err) {
  document.body.innerHTML = '<div style="padding:30px;font-family:monospace;background:#fff;">'
    + '<h2 style="color:#c00;">JS Error</h2>'
    + '<p><b>Message:</b> ' + msg + '</p>'
    + '<p><b>Line:</b> ' + line + ' Col: ' + col + '</p>'
    + '<p><b>Source:</b> ' + src + '</p>'
    + '<p><b>Stack:</b> ' + (err && err.stack ? err.stack : 'n/a') + '</p>'
    + '</div>';
  return true;
};
const API = '';

let navData = {};
let currentFilter = { cat: null, region: null };
let articles = [];
let searchTimer = null;
let activeTag = null;
let allTags = [];

// -- Init ----------------------------------------------------------------------

// -- Tabs ----------------------------------------------------------------------
function switchTab(tab) {
  ['feed','sources','dashboard','360','pdf'].forEach(t => {
    const el = document.getElementById('tab-'+t);
    if (el) el.classList.toggle('active', t === tab);
  });
  document.querySelector('.main').style.display = tab === 'feed' ? 'flex' : 'none';
  document.getElementById('panel-sources').classList.toggle('active', tab === 'sources');
  document.getElementById('panel-dashboard').classList.toggle('active', tab === 'dashboard');
  document.getElementById('panel-360').classList.toggle('active', tab === '360');
  document.getElementById('panel-pdf').classList.toggle('active', tab === 'pdf');
  if (tab === 'sources') loadSources();
  if (tab === 'dashboard') loadDashboard();
}

// -- Sources -------------------------------------------------------------------
let allSources = [];
const CAT_COLORS_JS = {
  'Europe en Régions':'#8b5cf6','DREETS':'#f97316','Régions':'#3b82f6',
  'Départements':'#10b981','Opérateur national':'#f59e0b','CARSAT':'#14b8a6',
  "Agence de l'eau":'#06b6d4','CRESS':'#ec4899'
};

async function loadSources() {
  try {
    allSources = await fetch(`${API}/api/sources`).then(r => r.json());
    renderSources(allSources);
  } catch(e) {
    document.getElementById('src-list').innerHTML = '<div class="state-box"><p>Erreur de chargement</p></div>';
  }
}

function renderSources(list) {
  var countEl = document.getElementById('src-count');
  var listEl = document.getElementById('src-list');
  countEl.textContent = list.length + ' sources';

  if (!list.length) {
    listEl.innerHTML = '<div class="state-box"><p>Aucune source</p></div>';
    return;
  }

  // Group by cat > region
  var groups = {};
  list.forEach(function(s) {
    var cat = s.cat || 'Sans catégorie';
    var region = s.region || '';
    if (!groups[cat]) groups[cat] = {};
    if (!groups[cat][region]) groups[cat][region] = [];
    groups[cat][region].push(s);
  });

  listEl.innerHTML = '';

  Object.keys(groups).sort().forEach(function(cat) {
    var catSources = Object.values(groups[cat]).flat();
    var color = (CAT_COLORS_JS && CAT_COLORS_JS[cat]) || '#4b5a75';

    // Folder wrapper
    var folder = document.createElement('div');
    folder.className = 'src-folder';
    folder.dataset.cat = cat;

    // Folder header
    var fHeader = document.createElement('div');
    fHeader.className = 'src-folder-header';
    fHeader.innerHTML = '<span class="src-folder-arrow">▼</span>' +
      '<div class="src-folder-dot" style="background:' + color + '"></div>' +
      '<span class="src-folder-name">' + escH(cat) + '</span>' +
      '<span class="src-folder-count">' + catSources.length + '</span>';
    fHeader.onclick = function() { toggleSrcFolder(fHeader); };
    folder.appendChild(fHeader);

    // Folder body
    var fBody = document.createElement('div');
    fBody.className = 'src-folder-body open';

    Object.keys(groups[cat]).sort().forEach(function(region) {
      var srcs = groups[cat][region];
      var container = fBody;

      if (region) {
        var sfolder = document.createElement('div');
        sfolder.className = 'src-subfolder';
        var sfHeader = document.createElement('div');
        sfHeader.className = 'src-subfolder-header';
        sfHeader.innerHTML = '<span class="src-subfolder-name">' + escH(region) + '</span>' +
          '<span class="src-subfolder-count">' + srcs.length + '</span>';
        sfolder.appendChild(sfHeader);
        var sfBody = document.createElement('div');
        sfBody.className = 'src-subfolder-body';
        sfolder.appendChild(sfBody);
        fBody.appendChild(sfolder);
        container = sfBody;
      }

      srcs.forEach(function(s) {
        var isDynamic = s.type === 'dynamic';
        var dotColor = (CAT_COLORS_JS && CAT_COLORS_JS[s.cat]) || '#4b5a75';

        var row = document.createElement('div');
        row.className = 'src-row';
        row.draggable = true;
        row.dataset.url = s.url;
        row.dataset.cat = s.cat;
        row.dataset.region = s.region || '';

        // Drag handle
        var drag = document.createElement('span');
        drag.className = 'src-row-drag';
        drag.title = 'Déplacer';
        drag.textContent = '⠿';
        row.appendChild(drag);

        // Color dot
        var dot = document.createElement('div');
        dot.className = 'src-dot';
        dot.style.background = dotColor;
        row.appendChild(dot);

        // Info
        var info = document.createElement('div');
        info.className = 'src-info';
        var nameDiv = document.createElement('div');
        nameDiv.className = 'src-name';
        nameDiv.textContent = s.name;
        var link = document.createElement('a');
        link.className = 'src-url';
        link.href = s.url;
        link.target = '_blank';
        link.textContent = s.url;
        link.onclick = function(e) { e.stopPropagation(); };
        info.appendChild(nameDiv);
        info.appendChild(link);
        row.appendChild(info);

        // Badges
        var badges = document.createElement('div');
        badges.className = 'src-row-badges';
        var catBadge = document.createElement('span');
        catBadge.className = 'src-cat-badge';
        catBadge.textContent = s.cat;
        badges.appendChild(catBadge);
        if (s.region) {
          var regBadge = document.createElement('span');
          regBadge.className = 'src-region-badge';
          regBadge.textContent = s.region;
          badges.appendChild(regBadge);
        }
        var typeBadge = document.createElement('span');
        typeBadge.className = 'src-badge ' + s.type;
        typeBadge.textContent = isDynamic ? 'Ajouté' : 'Intégré';
        badges.appendChild(typeBadge);
        row.appendChild(badges);

        // Actions
        var actions = document.createElement('div');
        actions.className = 'src-row-actions';

        var moveBtn = document.createElement('button');
        moveBtn.className = 'src-move-btn';
        moveBtn.title = 'Déplacer vers…';
        moveBtn.textContent = '↗';
        moveBtn.onclick = function(e) {
          e.stopPropagation();
          openMoveSource(s.url, s.cat, s.region || '');
        };
        actions.appendChild(moveBtn);

        var delBtn = document.createElement('button');
        delBtn.className = 'btn-del';
        delBtn.title = 'Supprimer' + (!isDynamic ? ' (source intégrée)' : '');
        delBtn.textContent = '✕';
        delBtn.onclick = function(e) {
          e.stopPropagation();
          var msg = isDynamic ? 'Supprimer cette source ?' : 'Supprimer cette source intégrée ? Elle ne sera plus scrapée.';
          if (confirm(msg)) deleteSource(encodeURIComponent(s.url));
        };
        actions.appendChild(delBtn);
        row.appendChild(actions);
        container.appendChild(row);
      });
    });

    folder.appendChild(fBody);
    listEl.appendChild(folder);
  });

  setupSourceDnD(listEl);
}


function toggleSrcFolder(header) {
  var body = header.nextElementSibling;
  var arrow = header.querySelector('.src-folder-arrow');
  body.classList.toggle('open');
  arrow.textContent = body.classList.contains('open') ? '▼' : '▶';
}

// Source drag & drop between folders
function setupSourceDnD(container) {
  var dragSrc = null;
  container.querySelectorAll('.src-row').forEach(function(row) {
    row.addEventListener('dragstart', function(e) {
      dragSrc = row;
      row.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', row.dataset.url);
    });
    row.addEventListener('dragend', function() {
      row.classList.remove('dragging');
      container.querySelectorAll('.src-row,.src-subfolder-body,.src-folder-body')
        .forEach(function(x){ x.classList.remove('drag-over'); });
    });
    row.addEventListener('dragover', function(e) {
      e.preventDefault(); e.stopPropagation();
      if (dragSrc && dragSrc !== row) row.classList.add('drag-over');
    });
    row.addEventListener('dragleave', function() { row.classList.remove('drag-over'); });
    row.addEventListener('drop', function(e) {
      e.preventDefault(); e.stopPropagation();
      row.classList.remove('drag-over');
      if (dragSrc && dragSrc !== row) {
        var srcCat = dragSrc.dataset.cat, srcRegion = dragSrc.dataset.region;
        var dstCat = row.dataset.cat, dstRegion = row.dataset.region;
        if (srcCat !== dstCat || srcRegion !== dstRegion) {
          // Move to different folder
          doMoveSource(dragSrc.dataset.url, dstCat, dstRegion);
        } else {
          // Same folder — reorder visually
          row.parentElement.insertBefore(dragSrc, row);
        }
        dragSrc = null;
      }
    });
  });

  // Drop zones on subfolder bodies
  container.querySelectorAll('.src-subfolder-body,.src-folder-body').forEach(function(zone) {
    zone.addEventListener('dragover', function(e) {
      if (dragSrc) { e.preventDefault(); zone.classList.add('drag-over'); }
    });
    zone.addEventListener('dragleave', function() { zone.classList.remove('drag-over'); });
    zone.addEventListener('drop', function(e) {
      e.preventDefault();
      zone.classList.remove('drag-over');
      if (!dragSrc) return;
      var folder = zone.closest('.src-folder');
      var subfolder = zone.closest('.src-subfolder');
      var toCat = folder ? folder.dataset.cat : dragSrc.dataset.cat;
      var toRegion = subfolder ? subfolder.querySelector('.src-subfolder-name').textContent : '';
      doMoveSource(dragSrc.dataset.url, toCat, toRegion);
      dragSrc = null;
    });
  });
}

function doMoveSource(url, toCat, toRegion) {
  fetch(API + '/api/sources/move', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({url: url, cat: toCat, region: toRegion || ''})
  }).then(function(r) {
    if (r.ok) { showToast('Source déplacée vers ' + toCat); loadSources(); loadNav(); }
    else showToast('Erreur: source intégrée non déplaçable');
  });
}

// Move source modal
function openMoveSource(url, currentCat, currentRegion) {
  var modal = document.getElementById('move-source-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'move-source-modal';
    modal.className = 'modal-overlay';

    var box = document.createElement('div');
    box.className = 'modal-box';
    box.style.maxWidth = '420px';

    var title = document.createElement('div');
    title.className = 'modal-title';
    title.textContent = 'Déplacer la source';

    var body = document.createElement('div');
    body.className = 'modal-body';

    var l1 = document.createElement('label');
    l1.className = 'form-label';
    l1.textContent = 'Dossier (catégorie)';
    var sel = document.createElement('select');
    sel.className = 'form-input';
    sel.id = 'move-src-cat';
    sel.style.cssText = 'width:100%;margin-bottom:10px';
    sel.onchange = function() { updateMoveRegions(this.value); };

    var l2 = document.createElement('label');
    l2.className = 'form-label';
    l2.textContent = 'Sous-dossier (région)';
    var inp = document.createElement('input');
    inp.className = 'form-input';
    inp.id = 'move-src-region';
    inp.placeholder = 'Laisser vide = racine du dossier';
    inp.style.width = '100%';

    body.appendChild(l1); body.appendChild(sel);
    body.appendChild(l2); body.appendChild(inp);

    var footer = document.createElement('div');
    footer.className = 'modal-footer';

    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn';
    cancelBtn.textContent = 'Annuler';
    cancelBtn.onclick = function() { modal.classList.remove('open'); };

    var confirmBtn = document.createElement('button');
    confirmBtn.className = 'btn btn-primary';
    confirmBtn.textContent = 'Déplacer';
    confirmBtn.onclick = confirmMoveSource;

    footer.appendChild(cancelBtn);
    footer.appendChild(confirmBtn);

    box.appendChild(title); box.appendChild(body); box.appendChild(footer);
    modal.appendChild(box);
    document.body.appendChild(modal);
  }

  // Populate cat options
  var cats = Object.keys(navData || {});
  var sel2 = document.getElementById('move-src-cat');
  sel2.innerHTML = '';
  cats.forEach(function(c) {
    var opt = document.createElement('option');
    opt.value = c;
    opt.textContent = c;
    if (c === currentCat) opt.selected = true;
    sel2.appendChild(opt);
  });

  modal._url = url;
  document.getElementById('move-src-region').value = currentRegion || '';
  modal.classList.add('open');
}


function updateMoveRegions(cat) {
  // Could populate region dropdown from navData
}

function confirmMoveSource() {
  var modal = document.getElementById('move-source-modal');
  var toCat = document.getElementById('move-src-cat').value;
  var toRegion = document.getElementById('move-src-region').value.trim();
  modal.classList.remove('open');
  doMoveSource(modal._url, toCat, toRegion);
}



function onNewCatChange(sel) {
  var customInput = document.getElementById('new-custom-cat');
  customInput.style.display = sel.value === '__new__' ? 'block' : 'none';
}

function createFolderFromPanel() {
  var modal = document.getElementById('create-folder-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'create-folder-modal';
    modal.className = 'modal-overlay';
    modal.onclick = function(e) { if (e.target === modal) modal.classList.remove('open'); };

    var box = document.createElement('div');
    box.className = 'modal-box cf-box';

    // Header
    var hdr = document.createElement('div');
    hdr.className = 'cf-header';
    var icon = document.createElement('span');
    icon.className = 'cf-icon';
    icon.textContent = '📁';
    var ttl = document.createElement('div');
    ttl.className = 'cf-title';
    ttl.textContent = 'Nouveau dossier';
    var closeBtn = document.createElement('button');
    closeBtn.className = 'cf-close';
    closeBtn.textContent = '✕';
    closeBtn.onclick = function() { modal.classList.remove('open'); };
    hdr.appendChild(icon); hdr.appendChild(ttl); hdr.appendChild(closeBtn);

    // Body
    var body = document.createElement('div');
    body.className = 'cf-body';

    var l1 = document.createElement('label');
    l1.className = 'cf-label';
    l1.textContent = 'Nom du dossier';
    var inp1 = document.createElement('input');
    inp1.className = 'cf-input';
    inp1.id = 'cf-cat';
    inp1.placeholder = 'Ex: Fondations, Agences…';

    var l2 = document.createElement('label');
    l2.className = 'cf-label';
    l2.textContent = 'Sous-dossier (optionnel)';
    var inp2 = document.createElement('input');
    inp2.className = 'cf-input';
    inp2.id = 'cf-region';
    inp2.placeholder = 'Laisser vide pour dossier racine';

    body.appendChild(l1); body.appendChild(inp1);
    body.appendChild(l2); body.appendChild(inp2);

    // Footer
    var footer = document.createElement('div');
    footer.className = 'cf-footer';

    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn';
    cancelBtn.textContent = 'Annuler';
    cancelBtn.onclick = function() { modal.classList.remove('open'); };

    var okBtn = document.createElement('button');
    okBtn.className = 'btn btn-primary';
    okBtn.textContent = '📁 Créer';
    okBtn.onclick = function() {
      var cat = document.getElementById('cf-cat').value.trim();
      var region = document.getElementById('cf-region').value.trim();
      if (!cat) { document.getElementById('cf-cat').focus(); return; }
      fetch(API + '/api/folders', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({cat: cat, region: region})
      }).then(function(r) {
        if (r.ok) {
          showToast('📁 Dossier "' + cat + '" créé');
          modal.classList.remove('open');
          document.getElementById('cf-cat').value = '';
          document.getElementById('cf-region').value = '';
          loadNav(); loadSources();
          // Update the cat dropdown in add-source form
          var sel = document.getElementById('new-cat');
          if (sel) {
            var exists = Array.from(sel.options).some(function(o){ return o.value === cat; });
            if (!exists) {
              var opt = document.createElement('option');
              opt.value = cat; opt.textContent = cat;
              sel.insertBefore(opt, sel.lastElementChild);
            }
            sel.value = cat;
          }
        } else { showToast('❌ Erreur création dossier'); }
      });
    };

    // Also allow Enter key
    inp1.onkeydown = inp2.onkeydown = function(e) { if (e.key === 'Enter') okBtn.click(); };

    footer.appendChild(cancelBtn); footer.appendChild(okBtn);
    box.appendChild(hdr); box.appendChild(body); box.appendChild(footer);
    modal.appendChild(box);
    document.body.appendChild(modal);
  }

  document.getElementById('cf-cat').value = '';
  document.getElementById('cf-region').value = '';
  modal.classList.add('open');
  setTimeout(function(){ document.getElementById('cf-cat').focus(); }, 80);
}

var _srcView = 'org';
function setSrcView(view) {
  _srcView = view;
  document.getElementById('view-org').classList.toggle('active', view === 'org');
  document.getElementById('view-list').classList.toggle('active', view === 'list');
  renderSources(allSources || []);
}

async function addSource() {
  var name = document.getElementById('new-name').value.trim();
  var catSel = document.getElementById('new-cat').value;
  var customCat = document.getElementById('new-custom-cat').value.trim();
  var cat = catSel === '__new__' ? customCat : catSel;
  var region = document.getElementById('new-region').value.trim();
  var url = document.getElementById('new-url').value.trim();
  if (!name || !url) { showToast('❌ Nom et URL requis'); return; }
  if (!cat) { showToast('❌ Choisissez ou créez un dossier'); return; }
  try {
    var res = await fetch(API + '/api/sources', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({name: name, cat: cat, region: region, url: url})
    });
    if (res.ok) {
      showToast('✅ Source ajoutée !');
      ['new-name','new-url','new-region'].forEach(function(id){ document.getElementById(id).value = ''; });
      loadSources(); loadNav();
    } else { showToast('❌ URL déjà existante ou erreur'); }
  } catch(e) { showToast('❌ Erreur réseau'); }
}

function filterSources(q) {
  var fl = q.toLowerCase();
  renderSources(fl
    ? allSources.filter(function(s){
        return s.name.toLowerCase().includes(fl) || s.cat.toLowerCase().includes(fl) ||
               (s.region||'').toLowerCase().includes(fl) || s.url.toLowerCase().includes(fl);
      })
    : allSources);
}

async function deleteSource(encodedUrl) {
  if (!confirm('Supprimer cette source ?')) return;
  await fetch(API + '/api/sources/' + encodedUrl, {method: 'DELETE'});
  showToast('🗑 Source supprimée');
  loadSources();
}

async function triggerScrape() {
  try {
    const resp = await fetch(`${API}/api/scrape`, {method: 'POST'});
    if (!resp.ok) throw new Error('scrape_failed');
    const data = await resp.json();
    showToast(`?? Scraping lanc? sur ${data.sources || 0} source(s)`);
    setProgress(35);
    await new Promise(r => setTimeout(r, 4000));
    await Promise.all([loadStats(), loadNav(), loadArticles()]);
    setProgress(100);
    setTimeout(() => setProgress(0), 800);
  } catch(e) {
    showToast('? Impossible de lancer le scraping');
    setProgress(0);
  }
}




// -- Dashboard ------------------------------------------------------------------
</script>
<script>
let dashCharts = {};
let dashData = {};
let dashLayout = 2;
let dashChartOrder = ['volume','donut','guichet','regions','tags','mechs','sectors','sources'];

// Available chart types
const CHART_TYPES = [
  { id:'volume',   icon:'📈', name:'Volume temporel',     desc:'Articles par jour',         span:2 },
  { id:'donut',    icon:'🍩', name:'Répartition types',   desc:'Dispositif / Actualité',    span:1 },
  { id:'guichet',  icon:'🏢', name:'Types de guichet',    desc:'Histogramme guichets',      span:1 },
  { id:'regions',  icon:'🗺', name:'Top régions',         desc:'Barres horizontales',       span:1 },
  { id:'tags',     icon:'🏷', name:'Top tags',            desc:'15 tags les plus fréquents',span:1 },
  { id:'mechs',    icon:'⚙', name:'Mécanismes',          desc:'AAP, Subvention, FEDER…',   span:1 },
  { id:'sectors',  icon:'🏭', name:'Secteurs',            desc:'Distribution thématique',   span:1 },
  { id:'sources',  icon:'📡', name:'Top sources',         desc:'Sources les plus actives',  span:1 },
  { id:'heatmap',  icon:'🔥', name:'Heatmap hebdo',       desc:'Activité par jour/semaine', span:2 },
  { id:'timeline', icon:'📅', name:'Frise chronologique', desc:'Dispositifs dans le temps', span:2 },
  { id:'ratio',    icon:'📊', name:'Ratio taggeré',       desc:'Évolution du taux de tag',  span:1 },
];

function jsAttr(value) {
  return JSON.stringify(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;');
}

function hideBrokenImage(img) {
  if (img) img.style.display = 'none';
}

function openArticleUrl(url) {
  if (url) window.open(url, '_blank', 'noopener');
}



function destroyCharts() {
  Object.values(dashCharts).forEach(c => { try { c.destroy(); } catch(e){} });
  dashCharts = {};
}

function setDashLayout(n) {
  dashLayout = n;
  ['1','2','3'].forEach(i => { const el=document.getElementById('layout-'+i); if(el) el.classList.toggle('active', i == n); });
  const grid = document.getElementById('charts-grid');
  if (grid) {
    grid.className = 'charts-grid' + (n===1?' cols-1':n===3?' cols-3':'');
  }
}

async function loadDashboard() {
  const period = document.getElementById('dash-period').value;
  const body = document.getElementById('dash-body');
  body.innerHTML = '<div class="state-box"><div class="spinner"></div><p>Analyse en cours…</p></div>';
  destroyCharts();
  try {
    const [stats, arts, tags] = await Promise.all([
      fetch(`${API}/api/stats`).then(r=>r.json()),
      fetch(`${API}/api/articles?limit=500`).then(r=>r.json()),
      fetch(`${API}/api/tags`).then(r=>r.json())
    ]);
    const now = Date.now();
    const days = parseInt(period);
    const filtered = days > 0 ? arts.filter(a => (now - new Date(a.scraped_at)) / 86400000 <= days) : arts;
    dashData = { stats, arts: filtered, tags, allArts: arts, days };
    renderDashboard();
  } catch(e) {
    body.innerHTML = '<div class="state-box"><p>❌ Erreur de chargement</p></div>';
  }
}

function renderDashboard() {
  const { stats, arts, tags, allArts, days } = dashData;
  const body = document.getElementById('dash-body');

  // Aggregations
  const byCat={}, byRegion={}, byDay={}, bySource={}, tagCounts={};
  const refTags={dispositif:0, actualite:0}, byMech={}, bySector={};
  const mechs=['AAP','AMI','AO','Subvention','Prêt','FEDER','FSE+','France 2030','ADEME','Bpifrance'];
  const sectors=['Agriculture','Industrie','Numérique','Énergie / Décarbonation / Sobriété','Tourisme','Logement / Bâtiment / Construction durable','Mobilité','Culture'];

  arts.forEach(a => {
    byCat[a.cat] = (byCat[a.cat]||0)+1;
    if (a.region) byRegion[a.region] = (byRegion[a.region]||0)+1;
    const day = (a.scraped_at||'').slice(0,10);
    if (day) byDay[day] = (byDay[day]||0)+1;
    bySource[a.source] = (bySource[a.source]||0)+1;
    (a.tags||[]).forEach(t => {
      tagCounts[t] = (tagCounts[t]||0)+1;
      if (t==='⭐ Dispositif') refTags.dispositif++;
      if (t==='⭐ Actualité') refTags.actualite++;
      if (mechs.includes(t)) byMech[t]=(byMech[t]||0)+1;
      if (sectors.includes(t)) bySector[t]=(bySector[t]||0)+1;
    });
  });

  const topN = (obj,n) => Object.entries(obj).sort((a,b)=>b[1]-a[1]).slice(0,n);
  const sortedDays = Object.entries(byDay).sort((a,b)=>a[0].localeCompare(b[0]));
  const taggedCount = arts.filter(a=>a.tags&&a.tags.length>0).length;
  const pctTagged = arts.length ? Math.round(taggedCount/arts.length*100) : 0;
  const notTagged = arts.length - taggedCount;

  // KPI trends (compare to previous period)
  const prevFiltered = days>0 ? allArts.filter(a=>{const d=(Date.now()-new Date(a.scraped_at))/86400000; return d>days&&d<=days*2;}) : [];
  const trendVal = (cur,prev) => prev===0 ? null : Math.round((cur-prev)/prev*100);
  const kpiTrend = (val) => val===null?'':val>=0?`<span class="kpi-trend up">+${val}%</span>`:`<span class="kpi-trend down">${val}%</span>`;

  // Store aggregations for drill-down
  dashData._agg = { byCat, byRegion, byDay, bySource, tagCounts, byMech, bySector, refTags, sortedDays, taggedCount, notTagged, pctTagged };

  const prevDisp = prevFiltered.filter(a=>(a.tags||[]).includes('⭐ Dispositif')).length;
  const prevTagged = prevFiltered.filter(a=>a.tags&&a.tags.length>0).length;

  const QUI = Object.keys(tagCounts).filter(t=>t.match(/PME|ETI|Grand|Collectivité|Association|Entreprise|Artisan|Agriculteur|Particulier|TPE|Startup/i));
  const QUE = Object.keys(tagCounts).filter(t=>sectors.includes(t)||mechs.includes(t));

  body.innerHTML = `
    <div class="dash-kpis">
      <div class="kpi-card" onclick="showDrilldown('all')">
        ${kpiTrend(trendVal(arts.length, prevFiltered.length))}
        <div class="kpi-label">Articles analysés</div>
        <div class="kpi-value">${arts.length}</div>
        <div class="kpi-sub">sur la période</div>
      </div>
      <div class="kpi-card" onclick="showDrilldown('dispositifs')">
        ${kpiTrend(trendVal(refTags.dispositif, prevDisp))}
        <div class="kpi-label">Dispositifs</div>
        <div class="kpi-value">${refTags.dispositif}</div>
        <div class="kpi-sub">${arts.length ? Math.round(refTags.dispositif/arts.length*100) : 0}% des articles</div>
      </div>
      <div class="kpi-card" onclick="showDrilldown('actualites')">
        <div class="kpi-label">Actualités</div>
        <div class="kpi-value">${refTags.actualite}</div>
        <div class="kpi-sub">${arts.length ? Math.round(refTags.actualite/arts.length*100) : 0}% des articles</div>
      </div>
      <div class="kpi-card" onclick="showDrilldown('tagged')">
        ${kpiTrend(trendVal(pctTagged, prevFiltered.length>0?Math.round(prevTagged/prevFiltered.length*100):0))}
        <div class="kpi-label">Taggerés</div>
        <div class="kpi-value">${pctTagged}%</div>
        <div class="kpi-sub">${taggedCount} / ${arts.length} articles</div>
      </div>
      <div class="kpi-card" onclick="showDrilldown('sources')">
        <div class="kpi-label">Sources actives</div>
        <div class="kpi-value">${Object.keys(bySource).length}</div>
        <div class="kpi-sub">sur la période</div>
      </div>
    </div>

    <div class="insight-row">
      <div class="insight-card">
        <div class="insight-title">📍 Régions actives</div>
        <div class="insight-list" id="ins-regions"></div>
      </div>
      <div class="insight-card">
        <div class="insight-title">👥 Bénéficiaires (QUI)</div>
        <div class="insight-list" id="ins-qui"></div>
      </div>
      <div class="insight-card">
        <div class="insight-title">🎯 Thématiques (QUE)</div>
        <div class="insight-list" id="ins-que"></div>
      </div>
    </div>

    <div class="charts-grid${dashLayout===1?' cols-1':dashLayout===3?' cols-3':''}" id="charts-grid"></div>

    <div style="margin-top:4px;">
      <button class="add-chart-btn" onclick="showChartPicker()">＋ Ajouter un graphique</button>
    </div>
  `;

  // Render insight lists
  const colors=['#3b82f6','#22c55e','#f59e0b','#a855f7','#06b6d4','#ef4444'];
  function renderInsightList(id, obj, keys) {
    const el = document.getElementById(id);
    if (!el) return;
    const items = (keys||Object.keys(obj)).filter(k=>obj[k]>0).sort((a,b)=>(obj[b]||0)-(obj[a]||0)).slice(0,6);
    const max = items[0] ? obj[items[0]] : 1;
    el.innerHTML = items.map((k,i)=>`
      <div class="insight-item" onclick="showDrilldown('tag',${jsAttr(k)})">
        <span class="insight-name" title="${k}">${k}</span>
        <div class="insight-bar-wrap"><div class="insight-bar-fill" style="width:${Math.round(obj[k]/max*100)}%;background:${colors[i%colors.length]}"></div></div>
        <span class="insight-count">${obj[k]}</span>
      </div>`).join('') || '<div style="font-size:11px;color:var(--muted)">—</div>';
  }
  renderInsightList('ins-regions', byRegion, null);
  renderInsightList('ins-qui', tagCounts, QUI);
  renderInsightList('ins-que', tagCounts, QUE.length?QUE:null);

  // Render charts in order
  destroyCharts();
  dashChartOrder.forEach(id => renderChartCard(id));
  setupDragDrop();
}

function renderChartCard(id) {
  const grid = document.getElementById('charts-grid');
  if (!grid) return;
  const type = CHART_TYPES.find(t=>t.id===id);
  if (!type) return;
  const span2 = (type.span===2 && dashLayout===2) ? 'span2' : '';
  const card = document.createElement('div');
  card.className = `chart-card ${span2}`;
  card.id = `card-${id}`;
  card.draggable = true;
  card.dataset.chartId = id;
  card.innerHTML = `
    <div class="chart-header">
      <span class="chart-drag-handle" title="Glisser pour réorganiser">⠿</span>
      <span class="chart-title">${type.icon} ${type.name}</span>
      <div class="chart-actions">
        <button class="chart-action-btn" onclick="exportChartPNG('${id}')" title="Exporter PNG">📷</button>
        <button class="chart-action-btn" onclick="exportChartCSV('${id}')" title="Exporter CSV">⬇</button>
        <button class="chart-action-btn" onclick="toggleChartSpan('${id}')" title="Agrandir/Réduire">⤢</button>
        <button class="chart-action-btn" onclick="removeChart('${id}')" title="Supprimer" style="color:var(--red);">✕</button>
      </div>
      <span class="chart-badge" id="badge-${id}">—</span>
    </div>
    <div class="chart-wrap"><canvas id="chart-${id}" height="220"></canvas></div>
  `;
  grid.appendChild(card);
  buildChart(id);
}

function buildChart(id) {
  const { byCat, byRegion, bySource, tagCounts, byMech, bySector, refTags, sortedDays, taggedCount, notTagged } = dashData._agg || {};
  if (!byCat) return;
  const canvas = document.getElementById('chart-'+id);
  if (!canvas) return;
  const topN = (obj,n) => Object.entries(obj).sort((a,b)=>b[1]-a[1]).slice(0,n);
  const COLORS = ['#1a3c2e','#2d6a4f','#c8e84e','#e8a020','#6b4fa8','#2d9e5f','#d94f3d','#3d8b6e','#7ab648','#5a7a1a','#a07030','#4a6a9e','#8a4f8a'];
  const setBadge = (id,v) => { const el=document.getElementById('badge-'+id); if(el) el.textContent=v; };
  // destroy old
  if (dashCharts[id] && dashCharts[id]._destroy) dashCharts[id]._destroy();
  dashCharts[id] = { _destroy: ()=>{} };

  if (id==='volume') {
    const labels=sortedDays.map(d=>d[0].slice(5)), data=sortedDays.map(d=>d[1]);
    setBadge(id, sortedDays.length+' jours');
    NanoChart.line(canvas, labels, [{data, color:'#3b82f6', fill:true, fillColor:'rgba(59,130,246,0.08)'}]);
  }
  else if (id==='donut') {
    const tagged=dashData.arts.filter(a=>a.tags&&a.tags.length>0).length;
    const disp=refTags.dispositif, actu=refTags.actualite, other=Math.max(0,tagged-disp-actu), none=dashData.arts.length-tagged;
    setBadge(id, dashData.arts.length+' articles');
    NanoChart.doughnut(canvas, ['Dispositif','Actualité','Autre','Non taggeré'], [disp,actu,other,none],
      ['#22c55e','#3b82f6','#a855f7','#e5e7eb']);
  }
  else if (id==='guichet') {
    const top=topN(byCat,8);
    setBadge(id, top.length+' types');
    NanoChart.bar(canvas, top.map(e=>e[0]||'?'), top.map(e=>e[1]), COLORS);
    canvas._onClick = (i,l) => showDrilldown('cat', l);
  }
  else if (id==='regions') {
    const top=topN(byRegion,10);
    setBadge(id, Object.keys(byRegion).length+' régions');
    NanoChart.bar(canvas, top.map(e=>e[0]), top.map(e=>e[1]), 'rgba(59,130,246,0.7)', {horizontal:true});
    canvas._onClick = (i,l) => showDrilldown('region', l);
  }
  else if (id==='tags') {
    const top=topN(tagCounts,15);
    setBadge(id, Object.keys(tagCounts).length+' tags');
    NanoChart.bar(canvas, top.map(e=>e[0]), top.map(e=>e[1]), COLORS, {horizontal:true});
    canvas._onClick = (i,l) => showDrilldown('tag', l);
  }
  else if (id==='mechs') {
    const top=topN(byMech,10);
    setBadge(id, top.reduce((s,e)=>s+e[1],0)+' articles');
    if (top.length===0) { canvas.closest('.chart-wrap').innerHTML='<div class="chart-empty">Aucun mécanisme détecté<br><small>Taggerez des articles</small></div>'; return; }
    NanoChart.polar(canvas, top.map(e=>e[0]), top.map(e=>e[1]), COLORS);
  }
  else if (id==='sectors') {
    const top=topN(bySector,8);
    setBadge(id, top.reduce((s,e)=>s+e[1],0)+' articles');
    if (top.length===0) { canvas.closest('.chart-wrap').innerHTML='<div class="chart-empty">Aucun secteur détecté<br><small>Taggerez des articles</small></div>'; return; }
    NanoChart.bar(canvas, top.map(e=>e[0].length>20?e[0].slice(0,18)+'…':e[0]), top.map(e=>e[1]), COLORS);
    canvas._onClick = (i,l) => showDrilldown('tag', top[i][0]);
  }
  else if (id==='sources') {
    const top=topN(bySource,10);
    setBadge(id, Object.keys(bySource).length+' sources');
    NanoChart.bar(canvas, top.map(e=>e[0].length>20?e[0].slice(0,18)+'…':e[0]), top.map(e=>e[1]), 'rgba(168,85,247,0.7)', {horizontal:true});
    canvas._onClick = (i,l) => showDrilldown('source', top[i][0]);
  }
  else if (id==='heatmap') {
    const days7=['Lun','Mar','Mer','Jeu','Ven','Sam','Dim'];
    const byWD=[0,0,0,0,0,0,0];
    dashData.arts.forEach(a=>{if(a.scraped_at){const d=new Date(a.scraped_at).getDay();byWD[(d+6)%7]++;}});
    setBadge(id,'Par jour de semaine');
    const mx=Math.max(...byWD);
    NanoChart.bar(canvas, days7, byWD, byWD.map(v=>v===mx?'#f59e0b':'rgba(59,130,246,0.5)'));
  }
  else if (id==='ratio') {
    const ratioByDay={};
    dashData.arts.forEach(a=>{
      const day=(a.scraped_at||'').slice(0,10); if(!day) return;
      if(!ratioByDay[day]) ratioByDay[day]={total:0,tagged:0};
      ratioByDay[day].total++;
      if(a.tags&&a.tags.length>0) ratioByDay[day].tagged++;
    });
    const sortedR=Object.entries(ratioByDay).sort((a,b)=>a[0].localeCompare(b[0]));
    setBadge(id,'% taggerés/jour');
    NanoChart.line(canvas, sortedR.map(d=>d[0].slice(5)),
      [{data:sortedR.map(d=>Math.round(d[1].tagged/d[1].total*100)), color:'#22c55e', fill:true, fillColor:'rgba(34,197,94,0.08)'}],
      {minY:0});
  }
  else if (id==='timeline') {
    const byWeek={};
    dashData.arts.forEach(a=>{
      if(!a.scraped_at) return;
      const d=new Date(a.scraped_at);
      const week=d.getFullYear()+'-W'+String(Math.ceil((d-new Date(d.getFullYear(),0,1))/604800000)).padStart(2,'0');
      byWeek[week]=(byWeek[week]||0)+1;
    });
    const sorted=Object.entries(byWeek).sort((a,b)=>a[0].localeCompare(b[0]));
    setBadge(id,'Par semaine');
    NanoChart.bar(canvas, sorted.map(d=>d[0]), sorted.map(d=>d[1]), 'rgba(6,182,212,0.7)');
  }
}

function toggleChartSpan(id) {
  const card = document.getElementById('card-'+id);
  if (card) card.classList.toggle('span2');
}

function removeChart(id) {
  dashChartOrder = dashChartOrder.filter(i=>i!==id);
  const card = document.getElementById('card-'+id);
  if (card) card.remove();
  if (dashCharts[id]) { dashCharts[id].destroy(); delete dashCharts[id]; }
}

function showChartPicker() {
  const existing = new Set(dashChartOrder);
  const overlay = document.createElement('div');
  overlay.className = 'chart-picker-overlay';
  const modal = document.createElement('div');
  modal.className = 'chart-picker-modal';
  modal.innerHTML = '<div class="chart-picker-header"><span class="chart-picker-title">Ajouter un graphique</span><button class="btn" style="font-size:11px;padding:5px 10px;">✕ Fermer</button></div><div class="chart-picker-body" id="cpm-body"></div>';
  modal.querySelector('button').onclick = () => overlay.remove();
  overlay.appendChild(modal);
  const body = modal.querySelector('#cpm-body');
  CHART_TYPES.forEach(t => {
    const card = document.createElement('div');
    card.className = 'chart-type-card';
    if (existing.has(t.id)) card.style.cssText = 'opacity:0.4;pointer-events:none;';
    card.innerHTML = '<div class="chart-type-icon">' + t.icon + '</div><div class="chart-type-name">' + t.name + '</div><div class="chart-type-desc">' + t.desc + '</div>' + (existing.has(t.id) ? '<div style="font-size:9px;color:var(--accent2);margin-top:4px;">✓ Déjà affiché</div>' : '');
    card.onclick = () => { addChart(t.id); overlay.remove(); };
    body.appendChild(card);
  });
  document.body.appendChild(overlay);
  overlay.addEventListener('click', e => { if(e.target===overlay) overlay.remove(); });
}

function addChart(id) {
  if (dashChartOrder.includes(id)) return;
  dashChartOrder.push(id);
  renderChartCard(id);
}

// -- Export functions --------------------------------------------------------
function exportChartPNG(id) {
  const canvas = document.getElementById('chart-'+id);
  if (!canvas) return;
  const link = document.createElement('a');
  link.download = `substanciel-${id}-${new Date().toISOString().slice(0,10)}.png`;
  link.href = canvas.toDataURL('image/png');
  link.click();
}

function exportChartCSV(id) {
  var agg = dashData._agg || {};
  var byCat = agg.byCat, byRegion = agg.byRegion, bySource = agg.bySource;
  var tagCounts = agg.tagCounts, byMech = agg.byMech, bySector = agg.bySector;
  var maps = { guichet:byCat, regions:byRegion, sources:bySource, tags:tagCounts, mechs:byMech, sectors:bySector };
  var map = maps[id];
  var NL = String.fromCharCode(10);
  var rows = [];
  if (id === 'volume') {
    var sortedDays = agg.sortedDays || [];
    rows.push('Date,Articles');
    sortedDays.forEach(function(d) { rows.push(d[0] + ',' + d[1]); });
  } else if (map) {
    var typeName = id;
    for (var ci = 0; ci < CHART_TYPES.length; ci++) {
      if (CHART_TYPES[ci].id === id) { typeName = CHART_TYPES[ci].name; break; }
    }
    rows.push(typeName + ',Nombre');
    Object.keys(map).sort(function(a,b){ return map[b]-map[a]; }).forEach(function(k) {
      rows.push(k + ',' + map[k]);
    });
  } else { return; }
  var csv = rows.join(NL);
  var blob = new Blob([csv], {type: 'text/csv;charset=utf-8;'});
  var link = document.createElement('a');
  link.download = 'substanciel-' + id + '-' + new Date().toISOString().slice(0,10) + '.csv';
  link.href = URL.createObjectURL(blob);
  link.click();
}

function exportDashboardPNG() {
  import('https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js').then(()=>{
    html2canvas(document.getElementById('dash-body'), {backgroundColor:'#f4f6f4'}).then(canvas=>{
      const link=document.createElement('a');
      link.download=`substanciel-dashboard-${new Date().toISOString().slice(0,10)}.png`;
      link.href=canvas.toDataURL('image/png');
      link.click();
    });
  }).catch(()=>alert('Export PNG du dashboard complet non disponible. Utilisez le bouton 📷 sur chaque graphique.'));
}

// -- Drill-down modal ---------------------------------------------------------
function showDrilldown(type, value) {
  if (!dashData.arts) return;
  let filtered = dashData.arts;
  let title = '';
  if (type==='all') { title='Tous les articles'; }
  else if (type==='dispositifs') { filtered=dashData.arts.filter(a=>(a.tags||[]).includes('⭐ Dispositif')); title='Dispositifs'; }
  else if (type==='actualites') { filtered=dashData.arts.filter(a=>(a.tags||[]).includes('⭐ Actualité')); title='Actualités'; }
  else if (type==='tagged') { filtered=dashData.arts.filter(a=>a.tags&&a.tags.length>0); title='Articles taggerés'; }
  else if (type==='sources') { filtered=dashData.arts; title='Sources actives'; }
  else if (type==='cat') { filtered=dashData.arts.filter(a=>a.cat===value); title=`Guichet : ${value}`; }
  else if (type==='region') { filtered=dashData.arts.filter(a=>a.region===value); title=`Région : ${value}`; }
  else if (type==='source') { filtered=dashData.arts.filter(a=>a.source===value); title=`Source : ${value}`; }
  else if (type==='tag') { filtered=dashData.arts.filter(a=>(a.tags||[]).includes(value)); title=`Tag : ${value}`; }

  window._drillFiltered = filtered;
  const overlay = document.createElement('div');
  overlay.className = 'drilldown-overlay';
  overlay.innerHTML = `
    <div class="drilldown-modal">
      <div class="drilldown-header">
        <span class="drilldown-title">🔍 ${title} <span style="font-size:11px;color:var(--muted);font-weight:400;">(${filtered.length} articles)</span></span>
        <div style="display:flex;gap:6px;">
          <button class="btn" onclick="exportDrilldownCSV()" style="font-size:10px;padding:5px 10px;">⬇ CSV</button>
          <button class="btn" onclick="this.closest('.drilldown-overlay').remove()" style="font-size:11px;padding:5px 10px;">✕</button>
        </div>
      </div>
      <div class="drilldown-body">
        ${filtered.length===0 ? '<div class="chart-empty">Aucun article dans cette catégorie</div>' : `
        <table class="drilldown-table">
          <thead><tr><th>Titre</th><th>Source</th><th>Région</th><th>Tags</th><th>Date</th></tr></thead>
          <tbody>${filtered.slice(0,200).map(a=>`
            <tr>
              <td><a href="${a.url||'#'}" target="_blank" style="color:var(--accent2);text-decoration:none;">${(a.title||'').slice(0,60)}${(a.title||'').length>60?'…':''}</a></td>
              <td style="color:var(--muted)">${(a.source||'').slice(0,25)}</td>
              <td>${a.region||'—'}</td>
              <td>${(a.tags||[]).slice(0,3).map(t=>`<span style="font-size:9px;background:rgba(59,130,246,0.1);color:var(--accent2);padding:1px 5px;border-radius:100px;margin-right:2px;">${t}</span>`).join('')}</td>
              <td style="color:var(--muted);white-space:nowrap">${(a.scraped_at||'').slice(0,10)}</td>
            </tr>`).join('')}
          </tbody>
        </table>`}
      </div>
    </div>`;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', e => { if(e.target===overlay) overlay.remove(); });
}

function exportDrilldownCSV() {
  var filtered = window._drillFiltered || [];
  var NL = String.fromCharCode(10);
  var DQ = String.fromCharCode(34);
  var rows = ['Titre,Source,URL,Region,Tags,Date'];
  filtered.forEach(function(a) {
    function esc(v) { return DQ + String(v || '').split(DQ).join(DQ+DQ) + DQ; }
    var tags = (a.tags || []).join(';');
    var date = String(a.scraped_at || '').slice(0, 10);
    rows.push([esc(a.title), esc(a.source), esc(a.url), esc(a.region), esc(tags), esc(date)].join(','));
  });
  var blob = new Blob([rows.join(NL)], {type: 'text/csv;charset=utf-8;'});
  var link = document.createElement('a');
  link.download = 'substanciel-drilldown-' + new Date().toISOString().slice(0,10) + '.csv';
  link.href = URL.createObjectURL(blob);
  link.click();
}

// -- Drag & Drop ---------------------------------------------------------------
function setupDragDrop() {
  const grid = document.getElementById('charts-grid');
  if (!grid) return;
  let dragging = null;
  grid.querySelectorAll('.chart-card').forEach(card => {
    card.addEventListener('dragstart', e => { dragging=card; setTimeout(()=>card.classList.add('dragging'),0); });
    card.addEventListener('dragend', () => { card.classList.remove('dragging'); dragging=null; });
    card.addEventListener('dragover', e => { e.preventDefault(); card.classList.add('drag-over'); });
    card.addEventListener('dragleave', () => card.classList.remove('drag-over'));
    card.addEventListener('drop', e => {
      e.preventDefault(); card.classList.remove('drag-over');
      if (!dragging || dragging===card) return;
      const all=[...grid.querySelectorAll('.chart-card')];
      const fromIdx=all.indexOf(dragging), toIdx=all.indexOf(card);
      if (fromIdx<toIdx) card.after(dragging); else card.before(dragging);
      dashChartOrder=([...grid.querySelectorAll('.chart-card')]).map(c=>c.dataset.chartId);
    });
  });
}


// -- 3-dot menu ----------------------------------------------------------------
function toggleMenu(e, id) {
  e.preventDefault(); e.stopPropagation();
  const menu = document.getElementById('menu-' + id);
  const isOpen = menu.classList.contains('open');
  closeAllMenus();
  if (!isOpen) {
    const btn = e.currentTarget || e.target;
    const rect = btn.getBoundingClientRect();
    menu.style.top = (rect.bottom + 4) + 'px';
    menu.style.right = (window.innerWidth - rect.right) + 'px';
    menu.style.left = 'auto';
    document.body.appendChild(menu);
    menu.classList.add('open');
  }
}
function closeAllMenus() { document.querySelectorAll('.card-menu.open').forEach(m => m.classList.remove('open')); }
document.addEventListener('click', closeAllMenus);
document.addEventListener('click', function(e) {
  if (e.target.closest('.card-pdf-btn')) e.stopPropagation();
});

function tagSingle(id) {
  closeAllMenus();
  selectedIds = new Set([id]);
  updateSelUI();
  tagSelected();
}

// -- Collect -------------------------------------------------------------------
</script>
<script>
let currentCollectData = null;
const GRID_FIELDS = ['guichet_financeur','guichet_instructeur','titre','nature','beneficiaire','type_depot','date_fermeture','objectif','types_depenses','operations_eligibles','depenses_eligibles','criteres_eligibilite','depenses_ineligibles','montants_taux','thematiques','territoire','points_vigilance','contact','programme_europeen'];
const GRID_LABELS = {guichet_financeur:'Guichet financeur',guichet_instructeur:'Guichet instructeur',titre:'Titre',nature:'Nature',beneficiaire:'Bénéficiaire',type_depot:'Type de dépôt',date_fermeture:'Date de fermeture',objectif:'Objectif',types_depenses:'Types de dépenses',operations_eligibles:'Opérations éligibles',depenses_eligibles:'Dépenses éligibles',criteres_eligibilite:"Critères d'éligibilité",depenses_ineligibles:'Dépenses inéligibles',montants_taux:"Montants et taux d'aide",thematiques:'Thématiques',territoire:'Territoire concerné',points_vigilance:'Points de vigilance',contact:'Contact',programme_europeen:'Programme européen'};

async function collectSelection() {
  const ids = Array.from(selectedIds);
  if (!ids.length) return;
  if (!confirm('Collecter automatiquement ' + ids.length + ' dispositif(s) via l\u2019IA ? Cela utilisera des crédits Claude.')) return;

  const btn = document.getElementById('btn-collect-sel');
  btn.disabled = true;
  btn.textContent = '⏳ Collecte en cours…';

  let done = 0, errors = 0;
  for (const id of ids) {
    const art = articles.find(a => a.id === id);
    if (!art) continue;
    btn.textContent = '⏳ ' + (done+1) + '/' + ids.length + ' en cours…';
    try {
      const res = await fetch(API + '/api/collect', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({title: art.title, url: art.url, summary: art.summary || '', article_id: id})
      });
      const data = await res.json();
      if (data.error) { errors++; }
      else { done++; }
    } catch(e) { errors++; }
  }

  btn.textContent = '📥 Collecter la sélection';
  btn.disabled = selectedIds.size === 0;
  showToast('✅ ' + done + ' dispositif(s) collecté(s)' + (errors ? ' — ' + errors + ' erreur(s)' : ''));
  // Rafraîchir la base de données
  await loadDatabase();
}

async function collectDispositif(articleId) {
  closeAllMenus();
  const art = articles.find(a => a.id === articleId);
  if (!art) return;
  document.getElementById('modal-title').textContent = '📥 ' + art.title.slice(0,70) + (art.title.length > 70 ? '…' : '');
  document.getElementById('modal-body').innerHTML = '<div class="modal-url">🔗 ' + art.url + '</div><div class="modal-status"><div class="spinner"></div><p>Claude analyse la fiche…<br><small>Extraction des 19 champs de la grille structurée</small></p></div>';
  document.getElementById('modal-footer').style.display = 'none';
  document.getElementById('collect-modal').classList.add('open');
  try {
    const res = await fetch(API + '/api/collect', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({id: articleId, url: art.url, title: art.title})
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    currentCollectData = data;
    renderCollectGrid(data, art.url);
    document.getElementById('btn-save-collect').style.display = '';
    document.getElementById('modal-footer').style.display = 'flex';
  } catch(e) {
    document.getElementById('modal-body').innerHTML = '<div class="modal-status"><p>❌ ' + e.message + '</p></div>';
    document.getElementById('modal-footer').style.display = 'flex';
    document.getElementById('btn-save-collect').style.display = 'none';
  }
}

function renderCollectGrid(data, url) {
  const rows = GRID_FIELDS.map(f => {
    const v = data[f]; const empty = !v || v === 'Information non fournie';
    return '<div class="grid-f"><div class="grid-f-label">' + GRID_LABELS[f] + '</div><div class="grid-f-val' + (empty?' empty':'') + '">' + (v||'Information non fournie') + '</div></div>';
  }).join('');
  document.getElementById('modal-body').innerHTML = (url ? '<div class="modal-url">🔗 ' + url + '</div>' : '') + rows;
}

async function saveCollect() {
  if (!currentCollectData) return;
  const btn = document.getElementById('btn-save-collect');
  btn.disabled = true; btn.textContent = '⏳…';
  try {
    await fetch(API + '/api/dispositifs', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(currentCollectData)});
    showToast('✅ Dispositif enregistré !');
    closeModal();
  } catch(e) { showToast('❌ Erreur'); }
  btn.disabled = false; btn.textContent = '💾 Enregistrer';
}

function closeModal() {
  document.getElementById('collect-modal').classList.remove('open');
  currentCollectData = null;
}

function exportPptx(id) {
  showToast('⏳ Génération du PowerPoint…');
  const a = document.createElement('a');
  a.href = API + '/api/dispositifs/' + id + '/export-pptx';
  a.download = 'dispositif.pptx';
  a.click();
}

// -- Database ------------------------------------------------------------------
let dispositifs = [];

async function loadDatabase() {
  document.getElementById('db-content').innerHTML = '<div class="state-box"><div class="spinner"></div></div>';
  try {
    dispositifs = await fetch(API + '/api/dispositifs').then(r => r.json());
    renderDatabase(dispositifs);
  } catch(e) {
    document.getElementById('db-content').innerHTML = '<div class="state-box"><p>❌ Erreur</p></div>';
  }
}

function renderDatabase(list) {
  if (!list.length) {
    document.getElementById('db-content').innerHTML = '<div class="state-box"><p>📭 Aucun dispositif.<br><small>Utilisez ⋮ sur un article puis "Collecter le dispositif"</small></p></div>';
    return;
  }
  const cols = [['titre','Titre'],['guichet_financeur','Financeur'],['nature','Nature'],['beneficiaire','Bénéficiaire'],['date_fermeture','Clôture'],['montants_taux','Montants'],['territoire','Territoire'],['thematiques','Thématiques']];
  document.getElementById('db-content').innerHTML = '<p style="font-size:11px;color:var(--muted);margin-bottom:12px;">' + list.length + ' dispositif(s) collecté(s)</p><div class="db-table-wrap"><table class="db-table"><thead><tr>' +
    cols.map(c => '<th>' + c[1] + '</th>').join('') + '<th>Actions</th></tr></thead><tbody>' +
    list.map(d => '<tr>' +
      cols.map(c => { const v=d[c[0]]; const e=!v||v==='Information non fournie'; return '<td><div class="db-cell' + (e?' db-empty':'') + '">' + (v||'—') + '</div></td>'; }).join('') +
      '<td style="white-space:nowrap"><button class="db-btn-sm" onclick="viewDispositif(' + d.id + ')" title="Voir">👁</button><button class="db-btn-sm" onclick="exportPptx(' + d.id + ')" title="Export PPTX" style="margin:0 3px">📊</button><button class="db-btn-sm db-btn-del" onclick="deleteDispositif(' + d.id + ')" title="Supprimer">✕</button></td></tr>'
    ).join('') + '</tbody></table></div>';
}

function viewDispositif(id) {
  const d = dispositifs.find(x => x.id === id);
  if (!d) return;
  currentCollectData = d;
  document.getElementById('modal-title').textContent = '📋 ' + (d.titre||'Dispositif');
  renderCollectGrid(d, d.source_url);
  document.getElementById('btn-save-collect').style.display = 'none';
  // Add/update PPT export button
  let pptBtn = document.getElementById('btn-export-ppt');
  if (!pptBtn) {
    pptBtn = document.createElement('button');
    pptBtn.id = 'btn-export-ppt';
    pptBtn.className = 'btn';
    pptBtn.style = 'background:rgba(139,92,246,0.1);border:1px solid rgba(139,92,246,0.3);color:#a78bfa;font-size:11px;padding:7px 14px;';
    pptBtn.textContent = '📊 Exporter PPT';
    document.getElementById('modal-footer').insertBefore(pptBtn, document.getElementById('modal-footer').firstChild);
  }
  pptBtn.onclick = () => exportPptx(id);
  document.getElementById('modal-footer').style.display = 'flex';
  document.getElementById('collect-modal').classList.add('open');
}

async function deleteDispositif(id) {
  if (!confirm('Supprimer ce dispositif ?')) return;
  await fetch(API + '/api/dispositifs/' + id, {method:'DELETE'});
  showToast('🗑 Supprimé'); loadDatabase();
}

function exportCSV() {
  if (!dispositifs.length) { showToast('Aucune donnée'); return; }
  const h = GRID_FIELDS.concat(['source_url','collected_at']);
  const rows = dispositifs.map(d => h.map(k => '"' + (d[k]||'').replace(/"/g,'""') + '"').join(','));
  const blob = new Blob([[h.join(',')].concat(rows).join('\\n')], {type:'text/csv;charset=utf-8;'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = 'dispositifs_' + new Date().toISOString().slice(0,10) + '.csv'; a.click();
}

async function init() {
  try {
    await Promise.race([
      Promise.all([loadStats(), loadNav(), loadTags()]),
      new Promise((_,reject) => setTimeout(() => reject(new Error('timeout')), 30000))
    ]);
    await loadArticles();
  } catch(e) {
    console.error('Init error:', e);
    const isTimeout = e.message === 'timeout';
    document.getElementById('feed').innerHTML = '<div class="state-box"><p>' +
      (isTimeout ? '⏳ Le serveur démarre, merci de patienter...' : '❌ Erreur de chargement') +
      ' <button class="btn btn-primary" onclick="init()" style="margin-left:8px">Réessayer</button></p></div>';
    if (isTimeout) setTimeout(init, 5000);
  }
}


// -- Selection -----------------------------------------------------------------
let selectedIds = new Set();

function handleCardClick(e, id) {
  // Don't interfere with checkbox clicks or link navigation
  if (e.target.type === 'checkbox') return;
  if (e.ctrlKey || e.metaKey || e.shiftKey) {
    e.preventDefault();
    toggleSelect(id);
  }
}

function onCheckChange(chk) {
  const id = parseInt(chk.dataset.id);
  if (chk.checked) selectedIds.add(id);
  else selectedIds.delete(id);
  updateSelUI();
}

function toggleSelect(id) {
  if (selectedIds.has(id)) selectedIds.delete(id);
  else selectedIds.add(id);
  const chk = document.getElementById(`chk-${id}`);
  const card = document.getElementById(`card-${id}`);
  if (chk) chk.checked = selectedIds.has(id);
  if (card) card.classList.toggle('selected', selectedIds.has(id));
  updateSelUI();
}

function selectAll() {
  articles.forEach(a => {
    selectedIds.add(a.id);
    const chk = document.getElementById(`chk-${a.id}`);
    const card = document.getElementById(`card-${a.id}`);
    if (chk) chk.checked = true;
    if (card) card.classList.add('selected');
  });
  updateSelUI();
}

function toggleSelectAll() {
  const allSelected = selectedIds.size === articles.length && articles.length > 0;
  if (allSelected) {
    selectNone();
  } else {
    selectAll();
  }
}

function selectNone() {
  selectedIds.clear();
  document.querySelectorAll('.card-check').forEach(c => c.checked = false);
  document.querySelectorAll('.card.selected').forEach(c => c.classList.remove('selected'));
  updateSelUI();
}

function updateSelUI() {
  const n = selectedIds.size;
  document.getElementById('sel-count').textContent = n;
  const wrap = document.getElementById('sel-count-wrap');
  if (wrap) wrap.style.display = n > 0 ? 'inline-flex' : 'none';
  document.getElementById('btn-tag').disabled = n === 0;
  const btnCS = document.getElementById('btn-collect-sel'); if (btnCS) btnCS.disabled = n === 0;
  const allSel = articles.length > 0 && n === articles.length;
  const btn = document.getElementById('btn-sel-toggle');
  const icon = document.getElementById('sel-toggle-icon');
  if (btn) {
    btn.classList.toggle('active', allSel);
    btn.innerHTML = (allSel ? '☑' : '☐') + ' Tout sélectionner';
    if (n > 0 && !allSel) btn.innerHTML = '☑ Tout sélectionner';
  }
}

async function tagSelected() {
  const ids = Array.from(selectedIds);
  if (!ids.length) return;

  const btn = document.getElementById('btn-tag');
  const prog = document.getElementById('tag-progress');
  const progFill = document.getElementById('tag-prog-fill');
  const progText = document.getElementById('tag-prog-text');
  const progPct = document.getElementById('tag-prog-pct');

  btn.disabled = true;
  prog.classList.add('show');

  let done = 0;
  for (const id of ids) {
    progText.textContent = `Tagging article ${done+1}/${ids.length}…`;
    try {
      const res = await fetch(`${API}/api/tag-article`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id})
      });
      const data = await res.json();
      if (data.tags) {
        // Update card live
        const card = document.getElementById(`card-${id}`);
        if (card) {
          let tagsDiv = card.querySelector('.card-tags');
          if (!tagsDiv) {
            tagsDiv = document.createElement('div');
            tagsDiv.className = 'card-tags';
            card.querySelector('.card-body').appendChild(tagsDiv);
          }
          tagsDiv.innerHTML = data.tags.map(t =>
            `<span class="card-tag ${t.includes('⭐') ? 'ref' : ''}">${t}</span>`
          ).join('');
        }
      }
    } catch(e) { console.error(e); }
    done++;
    const pct = Math.round(done/ids.length*100);
    progFill.style.width = pct + '%';
    progPct.textContent = pct + '%';
  }

  progText.textContent = `✅ ${done} article(s) taggeré(s) !`;
  progPct.textContent = '100%';
  setTimeout(() => {
    prog.classList.remove('show');
    progFill.style.width = '0%';
  }, 3000);

  selectNone();
  btn.disabled = false;
  showToast(`🏷 ${done} articles taggerés avec succès !`);
  loadTags();
}

// -- Tags ----------------------------------------------------------------------
async function loadTags() {
  try {
    allTags = await fetch(`${API}/api/tags`).then(r => r.json());
    renderTagBar(allTags);
  } catch(e) {}
}

function renderTagBar(tags) {
  const bar = document.getElementById('tag-bar');
  const top = tags.slice(0, 30); // Show top 30 tags
  bar.innerHTML = `<span style="font-size:10px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:0.08em;align-self:center;flex-shrink:0;">Tags :</span>
    <div class="tag-pill ${!activeTag ? 'active' : ''}" onclick="setTag(null)">Tous</div>
    ${top.map(t => `
      <div class="tag-pill ${t.tag.includes('⭐') ? 'ref' : ''} ${activeTag === t.tag ? 'active' : ''}" onclick="setTag(${jsAttr(t.tag)})">
        ${t.tag} <span style="opacity:0.6">${t.count}</span>
      </div>`).join('')}`;
}

function setTag(tag) {
  activeTag = tag;
  renderTagBar(allTags);
  loadArticles();
}

// -- Tag bar toggle -------------------------------------------------------------
let tagBarVisible = false;
function toggleTagBar() {
  tagBarVisible = !tagBarVisible;
  const bar = document.getElementById('tag-bar');
  const btn = document.getElementById('tag-bar-toggle');
  bar.style.display = tagBarVisible ? 'flex' : 'none';
  btn.textContent = tagBarVisible ? '▲' : '▼';
}

// -- Tagged only filter ---------------------------------------------------------
let taggedOnly = false;
function toggleTaggedOnly() {
  taggedOnly = !taggedOnly;
  const btn = document.getElementById('tagged-only-btn');
  if (btn) btn.classList.toggle('active', taggedOnly);
  const item = document.getElementById('drop-tagged');
  const chk = document.getElementById('check-tagged');
  if (item) item.classList.toggle('active', taggedOnly);
  if (chk) chk.textContent = taggedOnly ? '●' : '○';
  updateFilterDot();
  loadArticles();
}
function toggleFilterDrop() {
  const dd = document.getElementById('filter-dropdown');
  const btn = document.getElementById('btn-filter-drop');
  const rect = btn.getBoundingClientRect();
  dd.style.top = (rect.bottom + 4) + 'px';
  dd.style.left = rect.left + 'px';
  dd.classList.toggle('open');
}
function updateFilterDot() {
  const hasFilter = taggedOnly || cdcFilterActive;
  const btn = document.getElementById('btn-filter-drop');
  if (btn) btn.classList.toggle('has-active', hasFilter);
}
document.addEventListener('click', function(e) {
  if (!e.target.closest('#filter-dropdown-wrap')) {
    const dd = document.getElementById('filter-dropdown');
    if (dd) dd.classList.remove('open');
  }
});

// -- Veille 360- ---------------------------------------------------------------
</script>
<script>
const PROMPT_360 = `You are "Recherche 360°", a Senior Consultant in public and private financial engineering specialized exclusively in identifying CAPEX funding for investment projects carried by local authorities (communes, EPCI, departments, public institutions, EPL, SEM, SPL) or by private entities eligible for public investment aid.

Your sole mission is to conduct exhaustive strategic pre-screening whose unique objective is to verify that all schemes financing tangible assets have been identified before any detailed monitoring phase.

Your scope is strictly limited to CAPEX: real estate, works, construction, rehabilitation, technical equipment, industrial installations, productive tools, networks, energy performance, energy recovery and valorization systems, treatment systems, hydraulic or thermal loops, external developments, soil de-sealing, renaturation, water management, mobility integrated into an investment, and more generally any capitalizable tangible fixed asset.

You formally exclude operating expenses, facilitation/animation, standalone training, support without material investment, pure R&D not attached to a tangible demonstrator, standalone studies without works, and any marketing pack that does not explicitly point to a clearly identifiable CAPEX aid sheet.

You apply a strict three-criteria eligibility test: 1) Beneficiary legally compatible. 2) Eligible base explicitly finances tangible CAPEX. 3) Purpose coherent with project nature. If uncertain: conditional. If incompatible: out of CAPEX scope.

Your analysis follows a concentric logic: local → departmental → regional → national → European. Cover: building/rehabilitation, energy performance, water/sanitation, stormwater, biodiversity/renaturation, productive equipment, innovation linked to tangible asset, CEE, public loans.

Return a structured HTML table with columns: Thématique | Territoire | Financeur | Instructeur | Nom exact du dispositif | Type (subvention/prêt/prime) | Base CAPEX éligible | Pertinence stratégique | Montant/Taux indicatif | Statut | Lien officiel. Color-code rows: structurant=background #1a3a1a, complémentaire=background #1a2a3a, conditionnel=background #3a2a1a, hors CAPEX=background #3a1a1a. Never invent schemes or links. Conclude with exhaustiveness validation. Language: French. Return only clean HTML, no markdown.`;


function updateFileList() {
  const files = document.getElementById('v360-files').files;
  const list = document.getElementById('v360-file-list');
  if (files.length === 0) { list.textContent = ''; return; }
  list.textContent = Array.from(files).map(f => '📄 ' + f.name).join(' · ');
}

async function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function runVeille360() {
  const project = document.getElementById('v360-project').value.trim();
  if (!project) { alert("Veuillez décrire votre projet avant de lancer l'analyse."); return; }
  const btn = document.getElementById('v360-btn');
  const status = document.getElementById('v360-status');
  const result = document.getElementById('v360-result');
  btn.disabled = true;
  btn.textContent = '⏳ Analyse en cours…';
  status.textContent = 'Interrogation de Claude API…';
  result.style.display = 'none';
  try {
    const files = document.getElementById('v360-files').files;
    const messages_content = [];
    for (const file of files) {
      if (file.type === 'application/pdf') {
        const b64 = await fileToBase64(file);
        messages_content.push({ type: 'document', source: { type: 'base64', media_type: 'application/pdf', data: b64 } });
      } else {
        const text = await file.text();
        messages_content.push({ type: "text", text: `Document "${file.name}":\n` + text });
      }
    }
    messages_content.push({ type: 'text', text: project });
    const response = await fetch(`${API}/api/veille360`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: 'claude-sonnet-4-20250514', max_tokens: 4000, system: PROMPT_360, messages: [{ role: 'user', content: messages_content }] })
    });
    const data = await response.json();
    const html_result = (data.content && data.content.find(b => b.type === 'text') ? data.content.find(b => b.type === 'text').text : 'Aucun résultat.');
    result.style.display = 'block';
    result.innerHTML = '<div style="background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:16px;"><div style="font-size:11px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:12px;">📊 Résultats de la pré-analyse 360°</div><div style="font-size:12px;line-height:1.6;color:var(--text);overflow-x:auto;">' + html_result + '</div></div>';
    status.textContent = '✅ Analyse terminée';
  } catch(e) {
    status.textContent = '❌ Erreur: ' + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = '🔍 Lancer la pré-analyse 360°';
  }
}

function clearVeille360() {
  document.getElementById('v360-project').value = '';
  document.getElementById('v360-files').value = '';
  document.getElementById('v360-file-list').textContent = '';
  document.getElementById('v360-result').style.display = 'none';
  document.getElementById('v360-status').textContent = '';
}

// -- Stats ---------------------------------------------------------------------
async function loadStats() {
  try {
    const s = await fetch(`${API}/api/stats`).then(r => r.json());
    document.getElementById('st-total').textContent = s.total;
    document.getElementById('st-today').textContent = s.today;
    document.getElementById('st-ok2').textContent = s.sources_ok;
    document.getElementById('st-src').textContent = s.sources_total;
    document.getElementById('st-err').textContent = s.sources_error;
    document.getElementById('ts-total').textContent = s.total;
    document.getElementById('ts-today').textContent = s.today;
    document.getElementById('s-ok').textContent = s.sources_ok;
    document.getElementById('s-err').textContent = s.sources_error;
    if (s.tagged !== undefined) {
      document.getElementById('ts-total').textContent = s.total + ' (' + s.tagged + ' 🏷)';
    }
    document.getElementById('s-last').textContent = s.last_scrape
      ? new Date(s.last_scrape).toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'})
      : '—';
  } catch(e) { console.error(e); }
}

// -- Navigation ----------------------------------------------------------------
async function loadNav() {
  try {
    navData = await fetch(`${API}/api/nav`).then(r => r.json());
    renderNav(navData);
  } catch(e) { console.error(e); }
}

function renderNav(data, filterStr) {
  filterStr = filterStr || '';
  var container = document.getElementById('nav-scroll');
  var fl = filterStr.toLowerCase();
  var totalArticles = Object.values(data).reduce(function(s,c){ return s+c.total; }, 0);
  var html = '<div class="nav-all-row">' +
    '<div class="nav-all ' + (!currentFilter.cat ? 'active' : '') + '" onclick="setFilter(null,null)">' +
    '<span class="nav-all-label">Tous les articles</span>' +
    '<span class="nav-all-count">' + totalArticles + '</span></div>' +
    '<button class="nav-add-folder-btn" onclick="createFolderFromPanel()" title="Créer un nouveau dossier">📁</button>' +
    '</div>';

  var catEntries = Object.entries(data);
  catEntries.forEach(function(entry) {
    var cat = entry[0]; var catData = entry[1];
    if (fl && !cat.toLowerCase().includes(fl) &&
        !Object.keys(catData.regions).some(function(r){ return r.toLowerCase().includes(fl); })) return;
    var isOpen = catOpen[cat] !== undefined ? catOpen[cat] : (currentFilter.cat === cat);
    var isCatActive = currentFilter.cat === cat && !currentFilter.region;
    html += '<div class="nav-cat" draggable="true" data-cat="' + escH(cat) + '">' +
      '<div class="nav-cat-header ' + (isCatActive ? 'active' : '') + '" ' +
        'onclick="toggleCat(' + jsAttr(cat) + ')" ' +
        'oncontextmenu="navCtxCat(event,' + jsAttr(cat) + ')">' +
      '<span class="nav-drag-handle" title="Déplacer">⠿</span>' +
      '<div class="nav-cat-dot" style="background:' + (catData.color||'#4b5a75') + '"></div>' +
      '<span class="nav-cat-name">' + cat + '</span>' +
      '<span class="nav-cat-count">' + catData.total + '</span>' +
      '<span class="nav-cat-arrow ' + (isOpen ? 'open' : '') + '"></span>' +
      '</div>' +
      '<div class="nav-regions ' + (isOpen ? 'open' : '') + '">';
    var regions = Object.entries(catData.regions).sort(function(a,b){ return b[1]-a[1]; });
    regions.forEach(function(re2) {
      var region = re2[0]; var count = re2[1];
      if (fl && !region.toLowerCase().includes(fl) && !cat.toLowerCase().includes(fl)) return;
      var isRegionActive = currentFilter.cat === cat && currentFilter.region === region;
      html += '<div class="nav-region ' + (isRegionActive ? 'active' : '') + '" ' +
        'draggable="true" data-cat="' + escH(cat) + '" data-region="' + escH(region) + '" ' +
        'onclick="setFilter(' + jsAttr(cat) + ',' + jsAttr(region) + ')" ' +
        'oncontextmenu="navCtxRegion(event,' + jsAttr(cat) + ',' + jsAttr(region) + ')">' +
        '<span class="nav-region-drag">⠿</span>' +
        '<span class="nav-region-name">' + region + '</span>' +
        '<span class="nav-region-count">' + count + '</span>' +
        '</div>';
    });
    html += '</div></div>';
  });
  container.innerHTML = html;
  setupNavDnD();
  // Right-click on empty nav area → create folder
  var navScroll = document.getElementById('nav-scroll');
  if (navScroll) navScroll.oncontextmenu = function(e) {
    if (e.target === navScroll) { e.preventDefault(); createFolderFromPanel(); }
  };
}

// Track open/closed state independently of filter
var catOpen = {};
function toggleCat(cat) {
  if (catOpen[cat] === undefined) catOpen[cat] = !(currentFilter.cat === cat);
  else catOpen[cat] = !catOpen[cat];
  setFilter(cat, null);
}

// ── Sidebar Drag & Drop ──────────────────────────────────────────
function setupNavDnD() {
  var scroll = document.getElementById('nav-scroll');
  if (!scroll) return;
  var dragSrcCat = null, dragSrcRegion = null;

  // Cat-level drag (reorder folders)
  scroll.querySelectorAll('.nav-cat').forEach(function(el) {
    el.addEventListener('dragstart', function(e) {
      if (e.target.classList.contains('nav-region') || e.target.closest('.nav-region')) { e.stopPropagation(); return; }
      dragSrcCat = el.dataset.cat; dragSrcRegion = null;
      el.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', 'cat:' + el.dataset.cat);
    });
    el.addEventListener('dragend', function() {
      el.classList.remove('dragging');
      scroll.querySelectorAll('.nav-cat,.nav-region').forEach(function(x){ x.classList.remove('drag-over'); });
    });
    el.addEventListener('dragover', function(e) {
      e.preventDefault();
      if (dragSrcRegion) return; // region drag handled below
      if (dragSrcCat && dragSrcCat !== el.dataset.cat) el.classList.add('drag-over');
    });
    el.addEventListener('dragleave', function() { el.classList.remove('drag-over'); });
    el.addEventListener('drop', function(e) {
      e.preventDefault(); e.stopPropagation();
      el.classList.remove('drag-over');
      if (dragSrcRegion) return;
      if (dragSrcCat && dragSrcCat !== el.dataset.cat) {
        var srcEl = scroll.querySelector('.nav-cat[data-cat="' + CSS.escape(dragSrcCat) + '"]');
        if (srcEl) scroll.insertBefore(srcEl, el);
        dragSrcCat = null;
      }
    });
  });

  // Region-level drag (reorder or move to another folder)
  scroll.querySelectorAll('.nav-region').forEach(function(el) {
    el.addEventListener('dragstart', function(e) {
      e.stopPropagation();
      dragSrcCat = el.dataset.cat; dragSrcRegion = el.dataset.region;
      el.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', 'region:' + el.dataset.cat + ':' + el.dataset.region);
    });
    el.addEventListener('dragend', function() {
      el.classList.remove('dragging');
      scroll.querySelectorAll('.nav-region,.nav-cat').forEach(function(x){ x.classList.remove('drag-over'); });
    });
    el.addEventListener('dragover', function(e) {
      e.preventDefault(); e.stopPropagation();
      el.classList.add('drag-over');
    });
    el.addEventListener('dragleave', function() { el.classList.remove('drag-over'); });
    el.addEventListener('drop', function(e) {
      e.preventDefault(); e.stopPropagation();
      el.classList.remove('drag-over');
      if (!dragSrcRegion) return;
      var targetCat = el.dataset.cat;
      var targetRegion = el.dataset.region;
      // Same folder → reorder visually
      if (dragSrcCat === targetCat) {
        var parent = el.parentElement;
        var srcEl = parent.querySelector('.nav-region[data-region="' + CSS.escape(dragSrcRegion) + '"]');
        if (srcEl && srcEl !== el) parent.insertBefore(srcEl, el);
      } else {
        // Move region to another folder
        moveFolderToFolder(dragSrcCat, dragSrcRegion, targetCat);
      }
      dragSrcCat = null; dragSrcRegion = null;
    });
  });

  // Also allow dropping region onto a cat header (to move into that folder)
  scroll.querySelectorAll('.nav-cat-header').forEach(function(header) {
    var cat = header.closest('.nav-cat');
    header.addEventListener('dragover', function(e) {
      if (dragSrcRegion) { e.preventDefault(); cat.classList.add('drag-over'); }
    });
    header.addEventListener('dragleave', function() { cat.classList.remove('drag-over'); });
    header.addEventListener('drop', function(e) {
      e.preventDefault(); e.stopPropagation();
      cat.classList.remove('drag-over');
      if (dragSrcRegion && dragSrcCat !== cat.dataset.cat) {
        moveFolderToFolder(dragSrcCat, dragSrcRegion, cat.dataset.cat);
      }
      dragSrcCat = null; dragSrcRegion = null;
    });
  });
}

function moveFolderToFolder(fromCat, region, toCat) {
  // Visual: move the nav-region element
  var scroll = document.getElementById('nav-scroll');
  var srcEl = scroll.querySelector('.nav-region[data-cat="' + CSS.escape(fromCat) + '"][data-region="' + CSS.escape(region) + '"]');
  var targetRegionsEl = scroll.querySelector('.nav-cat[data-cat="' + CSS.escape(toCat) + '"] .nav-regions');
  if (srcEl && targetRegionsEl) {
    srcEl.dataset.cat = toCat;
    srcEl.setAttribute('onclick', 'setFilter(' + jsAttr(toCat) + ',' + jsAttr(region) + ')');
    srcEl.setAttribute('oncontextmenu', 'navCtxRegion(event,' + jsAttr(toCat) + ',' + jsAttr(region) + ')');
    targetRegionsEl.appendChild(srcEl);
    // Show target folder if closed
    targetRegionsEl.classList.add('open');
  }
  // Persist via API: move sources from fromCat/region to toCat/region
  fetch(API + '/api/sources/move-folder', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({from_cat: fromCat, region: region, to_cat: toCat})
  }).then(function() { loadNav(); }).catch(function(){});
}

// ── Sidebar Context Menus ────────────────────────────────────────
var _ctxMenu = null;
function removeCtxMenu() { if (_ctxMenu) { _ctxMenu.remove(); _ctxMenu = null; } }

function navCtxCat(e, cat) {
  e.preventDefault(); e.stopPropagation();
  removeCtxMenu();
  var m = document.createElement('div');
  m.className = 'nav-ctx-menu';
  m.style.cssText = 'top:' + e.clientY + 'px;left:' + e.clientX + 'px';
  m.innerHTML =
    '<div class="nav-ctx-item" onclick="createSubfolder(' + jsAttr(cat) + ');removeCtxMenu()">+ Créer un sous-dossier</div>' +
    '<div class="nav-ctx-sep"></div>' +
    '<div class="nav-ctx-item" onclick="setFilter(' + jsAttr(cat) + ',null);removeCtxMenu()">Voir ' + escH(cat) + '</div>' +
    '<div class="nav-ctx-item" onclick="collapseAll();removeCtxMenu()">Tout replier</div>' +
    '<div class="nav-ctx-item" onclick="expandAll();removeCtxMenu()">Tout déplier</div>' +
    '<div class="nav-ctx-sep"></div>' +
    '<div class="nav-ctx-item danger" onclick="deleteFolderPrompt(' + jsAttr(cat) + ',null);removeCtxMenu()">Supprimer le dossier</div>';
  document.body.appendChild(m); _ctxMenu = m;
  ensureCtxInView(m);
  setTimeout(function(){ document.addEventListener('click', removeCtxMenu, {once:true}); }, 10);
}

function navCtxRegion(e, cat, region) {
  e.preventDefault(); e.stopPropagation();
  removeCtxMenu();
  var m = document.createElement('div');
  m.className = 'nav-ctx-menu';
  m.style.cssText = 'top:' + e.clientY + 'px;left:' + e.clientX + 'px';
  m.innerHTML =
    '<div class="nav-ctx-item" onclick="setFilter(' + jsAttr(cat) + ',' + jsAttr(region) + ');removeCtxMenu()">Voir ' + escH(region) + '</div>' +
    '<div class="nav-ctx-item" onclick="renameRegionPrompt(' + jsAttr(cat) + ',' + jsAttr(region) + ');removeCtxMenu()">Renommer</div>' +
    '<div class="nav-ctx-sep"></div>' +
    '<div class="nav-ctx-item danger" onclick="deleteFolderPrompt(' + jsAttr(cat) + ',' + jsAttr(region) + ');removeCtxMenu()">Supprimer</div>';
  document.body.appendChild(m); _ctxMenu = m;
  ensureCtxInView(m);
  setTimeout(function(){ document.addEventListener('click', removeCtxMenu, {once:true}); }, 10);
}

function ensureCtxInView(el) {
  var r = el.getBoundingClientRect();
  if (r.bottom > window.innerHeight) el.style.top = (window.innerHeight - r.height - 8) + 'px';
  if (r.right > window.innerWidth) el.style.left = (window.innerWidth - r.width - 8) + 'px';
}

function createSubfolder(cat) {
  var region = prompt('Nom du sous-dossier dans "' + cat + '" :');
  if (!region || !region.trim()) return;
  fetch(API + '/api/folders', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({cat: cat, region: region.trim()})
  }).then(function(){ loadNav(); showToast('Sous-dossier créé'); });
}

function deleteFolderPrompt(cat, region) {
  var label = region ? '"' + region + '" (dans ' + cat + ')' : '"' + cat + '"';

  // Build confirmation modal
  var modal = document.getElementById('del-folder-modal');
  if (modal) modal.remove();

  modal = document.createElement('div');
  modal.id = 'del-folder-modal';
  modal.className = 'modal-overlay';
  modal.onclick = function(e) { if (e.target === modal) modal.remove(); };

  var box = document.createElement('div');
  box.className = 'modal-box df-box';

  // Header
  var hdr = document.createElement('div');
  hdr.className = 'df-header';
  var ttl = document.createElement('div');
  ttl.className = 'df-title';
  ttl.textContent = 'Supprimer ' + label;
  var closeBtn = document.createElement('button');
  closeBtn.className = 'cf-close';
  closeBtn.textContent = '✕';
  closeBtn.onclick = function() { modal.remove(); };
  hdr.appendChild(ttl); hdr.appendChild(closeBtn);

  // Body
  var body = document.createElement('div');
  body.className = 'df-body';

  // Option A — dossier seulement
  var optA = document.createElement('div');
  optA.className = 'df-option';
  optA.innerHTML = '<div class="df-opt-icon">📁</div>' +
    '<div class="df-opt-content">' +
      '<div class="df-opt-title">Supprimer le dossier uniquement</div>' +
      '<div class="df-opt-desc">Les articles et sources restent en base, le dossier disparaît de la navigation.</div>' +
    '</div>';
  optA.onclick = function() {
    doDeleteFolder(cat, region, false);
    modal.remove();
  };

  // Option B — tout purger
  var optB = document.createElement('div');
  optB.className = 'df-option df-option-danger';
  optB.innerHTML = '<div class="df-opt-icon">🗑</div>' +
    '<div class="df-opt-content">' +
      '<div class="df-opt-title">Tout supprimer</div>' +
      '<div class="df-opt-desc">Supprime le dossier <strong>ET</strong> tous les articles et sources associés. Action irréversible.</div>' +
    '</div>';
  optB.onclick = function() {
    doDeleteFolder(cat, region, true);
    modal.remove();
  };

  // Cancel
  var footer = document.createElement('div');
  footer.className = 'df-footer';
  var cancelBtn = document.createElement('button');
  cancelBtn.className = 'btn';
  cancelBtn.textContent = 'Annuler';
  cancelBtn.onclick = function() { modal.remove(); };
  footer.appendChild(cancelBtn);

  body.appendChild(optA);
  body.appendChild(optB);
  box.appendChild(hdr); box.appendChild(body); box.appendChild(footer);
  modal.appendChild(box);
  document.body.appendChild(modal);
  modal.classList.add('open');
}

function doDeleteFolder(cat, region, purge) {
  fetch(API + '/api/folders', {
    method: 'DELETE',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({cat: cat, region: region || '', purge: purge})
  }).then(function(r){ return r.json(); }).then(function(d){
    var msg = purge
      ? '🗑 Supprimé : ' + (d.deleted.articles||0) + ' articles, ' + (d.deleted.sources||0) + ' sources'
      : '📁 Dossier supprimé';
    showToast(msg);
    loadNav(); loadSources(); loadStats();
  });
}

function renameRegionPrompt(cat, region) {
  var newName = prompt('Nouveau nom pour "' + region + '" :', region);
  if (!newName || !newName.trim() || newName.trim() === region) return;
  // Move sources to new region name
  fetch(API + '/api/sources/move-folder', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({from_cat: cat, region: region, to_cat: cat, to_region: newName.trim()})
  }).then(function(){ loadNav(); showToast('Sous-dossier renommé'); });
}

function collapseAll() {
  Object.keys(navData||{}).forEach(function(c){ catOpen[c]=false; });
  renderNav(navData||{});
}
function expandAll() {
  Object.keys(navData||{}).forEach(function(c){ catOpen[c]=true; });
  renderNav(navData||{});
}

// Helper for HTML escaping in attributes
function escH(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }


function setFilter(cat, region) {
  currentFilter = { cat: cat, region: region };
  renderNav(navData);
  loadArticles();
  updateBreadcrumb();
}

function updateBreadcrumb() {
  var bc = document.getElementById('breadcrumb');
  if (!bc) return;
  if (!currentFilter.cat) {
    bc.innerHTML = '<strong>Tous les articles</strong>';
  } else if (!currentFilter.region) {
    bc.innerHTML = '<strong>' + escH(currentFilter.cat) + '</strong>';
  } else {
    bc.innerHTML = escH(currentFilter.cat) + ' › <strong>' + escH(currentFilter.region) + '</strong>';
  }
}

function filterNav(val) {
  renderNav(navData, val);
}

let cdcFilterActive = false;

function toggleCDCFilter() {
  cdcFilterActive = !cdcFilterActive;
  const item = document.getElementById('drop-cdc');
  const chk = document.getElementById('check-cdc');
  if (item) item.classList.toggle('active', cdcFilterActive);
  if (chk) chk.textContent = cdcFilterActive ? '●' : '○';
  updateFilterDot();
  loadArticles();
}

async function loadArticles() {
  document.getElementById('feed').innerHTML = '<div class="state-box"><div class="spinner"></div><p>Chargement…</p></div>';
  try {
    const params = new URLSearchParams({ limit: 1000 });
    if (currentFilter.cat) params.append('cat', currentFilter.cat);
    if (currentFilter.region) params.append('region', currentFilter.region);
    if (cdcFilterActive) params.append('has_cdc', '1');
    const q = document.getElementById('search').value.trim();
    if (q) params.append('q', q);
    if (activeTag) params.append('tag', activeTag);
    if (taggedOnly) params.append('has_tags', '1');

    articles = await fetch(`${API}/api/articles?${params}`).then(r => r.json());
    renderArticles(articles);
  } catch(e) {
    document.getElementById('feed').innerHTML = `<div class="state-box"><p>❌ Impossible de charger les articles.<br>Vérifiez la connexion au serveur.</p></div>`;
  }
}

function onSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadArticles, 400);
}

function renderArticles(list) {
  document.getElementById('feed-meta').textContent = `${list.length} résultat${list.length !== 1 ? 's' : ''}`;

  // Update feed title
  const title = currentFilter.region
    ? currentFilter.region
    : currentFilter.cat
    ? currentFilter.cat
    : 'Tous les articles';
  document.getElementById('feed-title').textContent = title;

  if (!list.length) {
    document.getElementById('feed').innerHTML = '<div class="state-box"><p>Aucun article trouvé.<br>Le scraper est peut-être encore en cours.</p></div>';
    return;
  }

  document.getElementById('feed').innerHTML = list.map((a, i) => {
    const domain = (() => { try { return new URL(a.url).hostname.replace('www.',''); } catch(e2) { return ''; } })();
    const img = a.image_url || ("https://www.google.com/s2/favicons?domain=" + domain + "&sz=64");
    const tags = a.tags && a.tags.length ? '<div class="card-tags">' + a.tags.map(function(t){ return '<span class="card-tag' + (t.includes('⭐') ? ' ref' : '') + '">' + t + '</span>'; }).join('') + '</div>' : '';
    const summary = a.summary ? '<div class="card-summary">' + a.summary + '</div>' : '';
    const region = a.region ? '<span class="card-region-badge">' + a.region + '</span>' : '';
    return '<div class="card" id="card-' + a.id + '" onclick="handleCardClick(event,' + a.id + ')" style="animation-delay:' + Math.min(i,40)*0.025 + 's">' +
      '<input type="checkbox" class="card-check" id="chk-' + a.id + '" data-id="' + a.id + '" onchange="onCheckChange(this)" onclick="event.stopPropagation()">' +
      '<div class="card-img-wrap"><img class="card-img" src="' + img + '" alt="" onerror="hideBrokenImage(this)" loading="lazy"></div>' +
      '<div class="card-body">' +
        '<div class="card-meta-row"><span class="card-source">' + (a.source||'') + '</span>' + region + '<span class="card-date">' + fmtDate(a.scraped_at) + '</span></div>' +
        '<div class="card-title-green"><a href="' + a.url + '" target="_blank" rel="noopener" onclick="event.stopPropagation()">' + a.title + '</a></div>' +
        summary + tags +
      '</div>' +
      '<div class="card-menu-wrap" onclick="event.stopPropagation()">' +
        (a.pdf_url ? '<a class="card-pdf-btn" href="' + a.pdf_url + '" target="_blank" rel="noopener" title="Ouvrir le cahier des charges" data-pdf="1">📋</a>' : '<span class="card-pdf-btn card-pdf-empty" title="Aucun CDC détecté au scraping — utilisez le volet CDC pour scanner">📋</span>') +
        '<button class="card-menu-btn" onclick="toggleMenu(event,' + a.id + ')">&#8942;</button>' +
        '<div class="card-menu" id="menu-' + a.id + '">' +
          '<div class="card-menu-item" onclick="openArticleUrl(' + jsAttr(a.url) + ')">Ouvrir la fiche</div>' +
          '<div class="card-menu-sep"></div>' +
          '<div class="card-menu-item" onclick="tagSingle(' + a.id + ')">Tagger cet article</div>' +
        '</div>' +
      '</div>' +
    '</div>';
  }).join('');
}


// ── PDF / Cahiers des charges ────────────────────────────────────────────────


// ── Cahiers des charges ──────────────────────────────────────────────────────

const CDC_EXTENSIONS = ['.pdf', '.doc', '.docx', '.png', '.jpg'];
const CDC_KEYWORDS = ['cahier','reglement','règlement','appel-a-projets',
  'appel_a_projets','notice','dossier','formulaire','guide','annexe',
  'modalites','candidature','depot','programme'];

async function fetchCDC(articleId) {
  showToast('📋 Recherche du cahier des charges...');
  try {
    const res = await fetch(API + '/api/articles/fetch-pdf', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({article_id: articleId})
    });
    if (!res.ok) { showToast('❌ Erreur serveur ' + res.status); return; }
    const data = await res.json();
    // Debug info dans la console
    if (data.debug) {
      console.log('[CDC Debug]', data.debug);
      if (data.debug.error) console.warn('[CDC Error]', data.debug.error);
      if (data.debug.ext_links) console.log('[CDC Links trouvés]', data.debug.ext_links);
    }
    if (data.error && !data.pdf_url) {
      showToast('❌ ' + data.error);
      return;
    }
    if (data.pdf_url) {
      showToast('✅ Document trouvé !');
      // Update card icon live
      const card = document.getElementById('card-' + articleId);
      if (card) {
        const emptyIcon = card.querySelector('.card-pdf-empty');
        if (emptyIcon) {
          const link = document.createElement('a');
          link.className = 'card-pdf-btn';
          link.href = data.pdf_url;
          link.target = '_blank';
          link.rel = 'noopener';
          link.title = 'Ouvrir le cahier des charges';
          link.textContent = '📋';
          emptyIcon.replaceWith(link);
        }
      }
    } else {
      showToast('❌ Aucun document trouvé sur cette page');
    }
  } catch(e) { showToast('❌ Erreur lors de la recherche'); }
}

async function cdcScanSelection() {
  const ids = Array.from(document.querySelectorAll('.card-check:checked')).map(c => parseInt(c.dataset.id));
  if (!ids.length) { showToast("Cochez des articles dans l'onglet Veille"); return; }
  await _runCDCScan(ids, false);
}

async function cdcScanAll() {
  const btn = document.getElementById('btn-pdf-scan-all');
  if (btn) { btn.disabled = true; btn.textContent = '\u23f3 Chargement…'; }
  let ids = [];
  try {
    // Charger TOUS les articles sans CDC (pas de limite, pas de filtre par dossier)
    const res = await fetch(API + '/api/articles?limit=2000');
    const data = await res.json();
    const all = Array.isArray(data) ? data : (data.articles || []);
    ids = all.filter(a => !a.pdf_url).map(a => a.id).filter(Boolean);
  } catch(e) {
    if (btn) { btn.disabled = false; btn.textContent = '🔍 Rechercher tous les CDC manquants'; }
    showToast('\u274c Erreur chargement articles'); return;
  }
  if (btn) { btn.disabled = false; btn.textContent = '🔍 Rechercher tous les CDC manquants'; }
  if (!ids.length) { showToast('\u2705 Aucun article sans CDC \u2014 tout est d\u00e9j\u00e0 à jour !'); return; }
  if (!confirm('Rechercher les CDC manquants sur ' + ids.length + ' article(s) ?')) return;
  await _runCDCScan(ids, false);
}

async function cdcAnalyzeAI() {
  const ids = Array.from(document.querySelectorAll('.card-check:checked')).map(c => parseInt(c.dataset.id));
  if (!ids.length) { showToast("Cochez des articles dans l'onglet Veille"); return; }
  if (!confirm('Analyse IA sur ' + ids.length + ' article(s) — utilise des credits Claude. Continuer ?')) return;
  await _runCDCScan(ids, true);
}

async function _runCDCScan(ids, useAI) {
  const status = document.getElementById('cdc-status');
  const list   = document.getElementById('cdc-results-list');
  const btns   = document.querySelectorAll('#panel-pdf button');
  btns.forEach(b => b.disabled = true);
  if (status) status.innerHTML = '<span style="color:var(--accent)">⏳ Scan lancé pour ' + ids.length + ' articles...</span>';
  if (list) list.innerHTML = '';

  try {
    const endpoint = useAI ? '/api/articles/fetch-pdf-ai' : '/api/articles/fetch-pdf-batch';
    const res = await fetch(API + endpoint, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({article_ids: ids})
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    // Polling toutes les 2s jusqu'à fin du job
    let lastDone = 0;
    const poll = async () => {
      try {
        const r = await fetch(API + '/api/articles/fetch-pdf-status');
        const job = await r.json();

        // Afficher progression
        if (status) {
          if (job.status === 'running') {
            const pct = job.total > 0 ? Math.round(job.done / job.total * 100) : 0;
            status.innerHTML = '<span style="color:var(--accent)">⏳ ' + job.done + ' / ' + job.total + ' articles scannés (' + pct + '%)</span>';
          } else if (job.status === 'done') {
            const found = (job.results || []).filter(r => r.doc_url).length;
            status.innerHTML = '<span style="color:var(--accent)">✅ Terminé — ' + job.done + ' scannés, ' + found + ' document(s) trouvé(s)</span>';
          } else if (job.status === 'error') {
            status.innerHTML = '<span style="color:#e05a3a">❌ Erreur : ' + (job.error || 'inconnue') + '</span>';
          }
        }

        // Afficher nouveaux résultats au fur et à mesure
        const newResults = (job.results || []).slice(lastDone);
        lastDone = (job.results || []).length;
        newResults.forEach(r => {
          if (!list) return;
          const docUrl = r.doc_url;
          const title  = r.title || ('Article #' + r.article_id);
          const ext    = docUrl ? docUrl.split('.').pop().toLowerCase().split('?')[0] : '';
          const icon   = ext === 'pdf' ? '📄' : (ext === 'docx' || ext === 'doc') ? '📝' : (ext === 'png' || ext === 'jpg') ? '🖼️' : '📋';
          const el = document.createElement('div');
          el.style.cssText = 'display:flex;align-items:center;gap:12px;padding:10px 14px;background:var(--surface);border-radius:10px;border:1px solid var(--border);margin-bottom:6px;' + (docUrl ? '' : 'opacity:0.4');
          if (docUrl) {
            el.innerHTML = '<span style="font-size:20px">' + icon + '</span>' +
              '<div style="flex:1;min-width:0">' +
                '<div style="font-size:13px;font-weight:600;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + title + '</div>' +
                '<div style="font-size:11px;color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + docUrl + (r.source==='ai'?' [IA]':'') + '</div>' +
              '</div>' +
              '<div style="display:flex;gap:6px;flex-shrink:0">' +
                '<a href="' + docUrl + '" target="_blank" rel="noopener" style="padding:5px 10px;background:var(--accent3);color:var(--bg);border-radius:6px;font-size:11px;font-weight:700;text-decoration:none">Ouvrir</a>' +
                '<a href="' + docUrl + '" download style="padding:5px 10px;background:var(--surface2);color:var(--accent);border:1px solid var(--border);border-radius:6px;font-size:11px;font-weight:700;text-decoration:none">⬇</a>' +
              '</div>';
          } else {
            el.innerHTML = '<span style="font-size:20px">❌</span><div style="font-size:13px;color:var(--text2)">' + title + '</div>';
          }
          list.appendChild(el);
        });

        if (job.status === 'running') {
          setTimeout(poll, 2000);
        } else {
          // Scan terminé : rafraîchir les cartes
          btns.forEach(b => b.disabled = false);
          await loadArticles();
        }
      } catch(e) {
        if (status) status.innerHTML = '<span style="color:#e05a3a">❌ Erreur polling : ' + e.message + '</span>';
        btns.forEach(b => b.disabled = false);
      }
    };
    setTimeout(poll, 1500);

  } catch(e) {
    if (status) status.innerHTML = '<span style="color:#e05a3a">❌ ' + e.message + '</span>';
    btns.forEach(b => b.disabled = false);
  }
}


// -- Refresh -------------------------------------------------------------------
async function doRefresh() {
  const btn = document.getElementById('btn-refresh');
  const spin = document.getElementById('spin');
  if (btn) btn.disabled = true;
  if (spin) { spin.style.display = 'inline'; spin.classList.add('on'); }
  setProgress(20);
  try {
    await fetch(`${API}/api/scrape`, { method: 'POST' });
    showToast('🔄 Scraping lancé — nouveaux articles dans quelques minutes');
    setProgress(50);
    await new Promise(r => setTimeout(r, 4000));
    await Promise.all([loadStats(), loadNav(), loadArticles()]);
    setProgress(100);
    setTimeout(() => setProgress(0), 800);
  } catch(e) { showToast('❌ Erreur serveur'); }
  if (btn) btn.disabled = false;
  if (spin) { spin.classList.remove('on'); spin.style.display = 'none'; }
}

// -- Helpers -------------------------------------------------------------------
function setProgress(p) {
  document.getElementById('progress').style.width = p + '%';
}

function fmtDate(d) {
  if (!d) return '';
  const diff = Math.floor((Date.now() - new Date(d)) / 60000);
  if (diff < 1) return "À l'instant";
  if (diff < 60) return `il y a ${diff}min`;
  if (diff < 1440) return `il y a ${Math.floor(diff/60)}h`;
  return new Date(d).toLocaleDateString('fr-FR', {day:'numeric', month:'short'});
}

function showToast(msg) {
  const t = document.createElement('div');
  t.className = 'toast'; t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// Auto-refresh stats every 5 min
setInterval(() => { loadStats(); loadNav(); }, 300000);

init();

</script>


<!-- MODAL AUTO-TAG AGENT -->
<div id="autotag-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;align-items:center;justify-content:center;">
  <div style="background:var(--surface);border-radius:14px;padding:28px;width:420px;max-width:94vw;box-shadow:0 20px 60px rgba(0,0,0,.3);">
    <div style="font-family:Syne,sans-serif;font-weight:800;font-size:17px;margin-bottom:4px">&#129302; Agent Curation IA</div>
    <div style="font-size:12px;color:var(--muted);margin-bottom:20px">Tagger automatiquement les articles avec Claude Haiku</div>
    <div style="display:flex;flex-direction:column;gap:12px;margin-bottom:20px">
      <label style="font-size:12px;display:flex;align-items:center;gap:8px;cursor:pointer">
        <input type="checkbox" id="at-only-untagged" checked style="accent-color:var(--accent)">
        Traiter uniquement les articles non tagés
      </label>
      <label style="font-size:12px;display:flex;align-items:center;gap:8px;cursor:pointer">
        <input type="checkbox" id="at-delete-irrelevant" style="accent-color:#c0392b">
        <span>Supprimer les articles non pertinents <span style="color:#c0392b;font-weight:700">(irréversible)</span></span>
      </label>
      <label style="font-size:12px;display:flex;flex-direction:column;gap:4px">
        Nombre d’articles à traiter :
        <input type="number" id="at-limit" value="50" min="5" max="200" style="padding:6px 10px;border:1px solid var(--border);border-radius:6px;font-size:12px;width:100px">
      </label>
    </div>
    <div id="autotag-progress" style="display:none;margin-bottom:16px">
      <div style="height:6px;background:var(--surface2);border-radius:4px;overflow:hidden;margin-bottom:8px">
        <div id="at-bar" style="height:100%;background:var(--lime);border-radius:4px;width:0%;transition:width .3s"></div>
      </div>
      <div id="at-status-text" style="font-size:11px;color:var(--muted)">Initialisation…</div>
    </div>
    <div style="display:flex;gap:8px;justify-content:flex-end">
      <button onclick="closeAutoTagPanel()" style="padding:8px 16px;border-radius:8px;border:1px solid var(--border);background:var(--surface2);cursor:pointer;font-size:12px">Annuler</button>
      <button id="at-start-btn" onclick="startAutoTag()" style="padding:8px 18px;border-radius:8px;border:none;background:var(--accent);color:var(--lime);font-weight:800;cursor:pointer;font-size:12px">&#9654; Lancer</button>
    </div>
  </div>
</div>

<script>
// ── AUTO-TAG AGENT ──────────────────────────────────────────────
function openAutoTagPanel() {
  document.getElementById('autotag-modal').style.display = 'flex';
  document.getElementById('autotag-progress').style.display = 'none';
  document.getElementById('at-start-btn').disabled = false;
  document.getElementById('at-start-btn').textContent = '\u25b6 Lancer';
}
function closeAutoTagPanel() {
  document.getElementById('autotag-modal').style.display = 'none';
}
function startAutoTag() {
  const limit = parseInt(document.getElementById('at-limit').value) || 50;
  const onlyUntagged = document.getElementById('at-only-untagged').checked;
  const deleteIrr = document.getElementById('at-delete-irrelevant').checked;
  document.getElementById('at-start-btn').disabled = true;
  document.getElementById('autotag-progress').style.display = 'block';
  document.getElementById('at-status-text').textContent = 'D\u00e9marrage\u2026';
  fetch(API + '/api/auto-tag', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({limit, only_untagged: onlyUntagged, delete_irrelevant: deleteIrr})
  }).then(r => r.json()).then(d => {
    if (d.error) { showToast('\u26a0 ' + d.error); return; }
    if (d.status === 'no_articles') { showToast('Aucun article \u00e0 traiter'); return; }
    pollAutoTagStatus();
  }).catch(e => showToast('\u26a0 Erreur r\u00e9seau'));
}
function pollAutoTagStatus() {
  fetch(API + '/api/auto-tag/status').then(r => r.json()).then(d => {
    const bar = document.getElementById('at-bar');
    const txt = document.getElementById('at-status-text');
    bar.style.width = d.progress + '%';
    txt.textContent = d.done + '/' + d.total + ' articles \u2014 ' + d.tagged + ' tag\u00e9s, ' + (d.skipped||0) + ' ignor\u00e9s, ' + d.errors + ' erreurs';
    if (d.status === 'running') {
      setTimeout(pollAutoTagStatus, 1500);
    } else {
      txt.textContent = '\u2705 Termin\u00e9 ! ' + d.tagged + ' article(s) tag\u00e9(s) \u2014 dont heuristiques, ' + (d.skipped||0) + ' ignor\u00e9s';
      document.getElementById('at-start-btn').textContent = '\u2713 Fait';
      setTimeout(function(){ closeAutoTagPanel(); loadArticles(); }, 2000);
    }
  });
}
// ────────────────────────────────────────────────────────────────
</script>

</body>
</html>
"""


@app.route('/api/veille360', methods=['POST'])
def api_veille360():
    import json as _json
    data = request.get_json(force=True)
    if not ANTHROPIC_API_KEY:
        return jsonify({'error': 'ANTHROPIC_API_KEY manquant'}), 500
    try:
        payload = _json.dumps({
            'model': data.get('model', 'claude-sonnet-4-20250514'),
            'max_tokens': data.get('max_tokens', 4000),
            'system': data.get('system', ''),
            'messages': data.get('messages', [])
        }).encode('utf-8')
        req = Request(
            'https://api.anthropic.com/v1/messages',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01'
            }
        )
        with urlopen(req, timeout=120) as resp:
            result = _json.loads(resp.read().decode('utf-8'))
        return jsonify(result)
    except Exception as e:
        log.error(f'veille360 error: {e}')
        return jsonify({'error': str(e)}), 500


# ── Folder management ─────────────────────────────────────────────────────────
@app.route('/api/veille360/sessions', methods=['GET'])
def get_veille360_sessions():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id, client_name, project_desc, created_at FROM veille360_sessions ORDER BY created_at DESC")
    rows = cur.fetchall(); cur.close(); conn.close()
    return jsonify([{**dict(r), 'created_at': r['created_at'].isoformat()} for r in rows])

@app.route('/api/veille360/sessions', methods=['POST'])
def save_veille360_session():
    data = request.get_json()
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO veille360_sessions (client_name, project_desc, result_html) VALUES (%s, %s, %s) RETURNING id",
        (data.get('client_name', 'Sans nom'), data.get('project_desc', ''), data.get('result_html', ''))
    )
    new_id = cur.fetchone()['id']
    conn.commit(); cur.close(); conn.close()
    return jsonify({'id': new_id, 'status': 'saved'})

@app.route('/api/veille360/sessions/<int:sid>', methods=['GET'])
def get_veille360_session(sid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM veille360_sessions WHERE id=%s", (sid,))
    row = cur.fetchone(); cur.close(); conn.close()
    if not row: return jsonify({'error': 'not found'}), 404
    d = dict(row); d['created_at'] = d['created_at'].isoformat()
    return jsonify(d)

@app.route('/api/veille360/sessions/<int:sid>', methods=['DELETE'])
def delete_veille360_session(sid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM veille360_sessions WHERE id=%s", (sid,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({'status': 'deleted'})

@app.route('/api/journal', methods=['GET'])
def get_journal_editions():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id, title, edition_date, created_at FROM journal_editions ORDER BY created_at DESC LIMIT 20")
    rows = cur.fetchall(); cur.close(); conn.close()
    return jsonify([{**dict(r), 'edition_date': str(r['edition_date']), 'created_at': r['created_at'].isoformat()} for r in rows])

@app.route('/api/journal/<int:jid>', methods=['GET'])
def get_journal_edition(jid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM journal_editions WHERE id=%s", (jid,))
    row = cur.fetchone(); cur.close(); conn.close()
    if not row: return jsonify({'error': 'not found'}), 404
    d = dict(row); d['edition_date'] = str(d['edition_date']); d['created_at'] = d['created_at'].isoformat()
    return jsonify(d)

@app.route('/api/journal', methods=['POST'])
def save_journal_edition():
    data = request.get_json()
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO journal_editions (title, summaries) VALUES (%s, %s) RETURNING id",
        (data.get('title', 'Journal SubstanCiel'), json.dumps(data.get('summaries', []))))
    new_id = cur.fetchone()['id']
    conn.commit(); cur.close(); conn.close()
    return jsonify({'id': new_id, 'status': 'saved'})

@app.route('/api/journal/<int:jid>', methods=['DELETE'])
def delete_journal_edition(jid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM journal_editions WHERE id=%s", (jid,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({'status': 'deleted'})

@app.route('/api/journal/summarize', methods=['POST'])
def summarize_articles():
    if not ANTHROPIC_API_KEY:
        return jsonify({'error': 'ANTHROPIC_API_KEY not configured'}), 500
    data = request.get_json()
    articles_to_summarize = data.get('articles', [])
    if not articles_to_summarize:
        return jsonify({'error': 'No articles provided'}), 400
    SUMMARIZE_PROMPT = "Tu es redacteur editorial du Journal SubstanCiel, veille sur les financements et politiques publiques. Redige un resume journalistique de 5 a 6 phrases : contextualise le sujet, explique les enjeux pour les acteurs concernes, et mentionne les elements cles (montants, calendrier, territoires si disponibles). Style clair, informatif, sans jargon. Reponds UNIQUEMENT en JSON : {\"summary\": \"...\", \"category\": \"...\", \"importance\": \"haute|normale\"}"
    summaries = []
    for art in articles_to_summarize[:24]:
        try:
            user_content = "Titre : " + art.get('title','') + "\nSource : " + art.get('source','') + "\nResume : " + (art.get('summary','') or '')
            payload = json.dumps({"model": "claude-haiku-4-5-20251001", "max_tokens": 400, "system": SUMMARIZE_PROMPT, "messages": [{"role": "user", "content": user_content}]}).encode()
            req = Request("https://api.anthropic.com/v1/messages", data=payload, headers={"Content-Type": "application/json", "x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"}, method="POST")
            with urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
            text = result["content"][0]["text"].strip()
            m = re.search(r'\{[\s\S]*\}', text)
            parsed = json.loads(m.group() if m else text)
            summaries.append({"title": art.get("title",""), "source": art.get("source",""), "url": art.get("url",""), "date": (art.get("scraped_at","") or "")[:10], "summary": parsed.get("summary",""), "category": parsed.get("category",""), "importance": parsed.get("importance","normale")})
        except Exception:
            summaries.append({"title": art.get("title",""), "source": art.get("source",""), "url": art.get("url",""), "date": (art.get("scraped_at","") or "")[:10], "summary": art.get("summary","") or "Resume non disponible.", "category": "", "importance": "normale"})
    return jsonify({"summaries": summaries})


@app.route('/api/folders', methods=['GET'])
def api_get_folders():
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT cat, region, sort_order FROM custom_folders ORDER BY sort_order, cat, region")
    rows=[dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/api/folders', methods=['POST'])
def api_create_folder():
    data=request.get_json(force=True)
    cat=data.get('cat','').strip()
    region=data.get('region','').strip()
    if not cat:
        return jsonify({'error':'cat required'}),400
    try:
        conn=get_db(); cur=conn.cursor()
        cur.execute("INSERT INTO custom_folders(cat,region,sort_order) VALUES(%s,%s,0) ON CONFLICT(cat,region) DO NOTHING",(cat,region))
        conn.commit(); conn.close()
        return jsonify({'ok':True})
    except Exception as e:
        return jsonify({'error':str(e)}),500

@app.route('/api/folders', methods=['DELETE'])
def api_delete_folder():
    data=request.get_json(force=True)
    cat=data.get('cat','').strip()
    region=data.get('region','').strip()
    purge=data.get('purge', False)  # if True: delete articles + sources too
    if not cat:
        return jsonify({'error':'cat required'}),400
    conn=get_db(); cur=conn.cursor()
    deleted={'articles':0,'sources':0,'folders':0}
    if purge:
        if region:
            cur.execute("SELECT COUNT(*) as n FROM articles WHERE cat=%s AND region=%s",(cat,region))
            deleted['articles']=cur.fetchone()['n']
            cur.execute("DELETE FROM articles WHERE cat=%s AND region=%s",(cat,region))
            cur.execute("SELECT COUNT(*) as n FROM sources_custom WHERE cat=%s AND region=%s",(cat,region))
            deleted['sources']=cur.fetchone()['n']
            cur.execute("DELETE FROM sources_custom WHERE cat=%s AND region=%s",(cat,region))
        else:
            cur.execute("SELECT COUNT(*) as n FROM articles WHERE cat=%s",(cat,))
            deleted['articles']=cur.fetchone()['n']
            cur.execute("DELETE FROM articles WHERE cat=%s",(cat,))
            cur.execute("SELECT COUNT(*) as n FROM sources_custom WHERE cat=%s",(cat,))
            deleted['sources']=cur.fetchone()['n']
            cur.execute("DELETE FROM sources_custom WHERE cat=%s",(cat,))
    if region:
        cur.execute("DELETE FROM custom_folders WHERE cat=%s AND region=%s",(cat,region))
        deleted['folders']=cur.rowcount
    else:
        cur.execute("DELETE FROM custom_folders WHERE cat=%s",(cat,))
        deleted['folders']=cur.rowcount
    conn.commit(); conn.close()
    return jsonify({'ok':True,'deleted':deleted})

@app.route('/api/sources/move-folder', methods=['POST'])
def api_move_folder():
    """Move/rename all sources from one cat/region to another"""
    data=request.get_json(force=True)
    from_cat=data.get('from_cat','').strip()
    region=data.get('region','').strip()
    to_cat=data.get('to_cat','').strip()
    to_region=data.get('to_region', region).strip()
    if not from_cat or not to_cat:
        return jsonify({'error':'from_cat and to_cat required'}),400
    conn=get_db(); cur=conn.cursor()
    # Update sources_custom
    cur.execute("UPDATE sources_custom SET cat=%s,region=%s WHERE cat=%s AND region=%s",(to_cat,to_region,from_cat,region))
    # Update articles
    cur.execute("UPDATE articles SET cat=%s,region=%s WHERE cat=%s AND region=%s",(to_cat,to_region,from_cat,region))
    # Update custom_folders
    cur.execute("UPDATE custom_folders SET cat=%s,region=%s WHERE cat=%s AND region=%s",(to_cat,to_region,from_cat,region))
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/api/sources/move', methods=['POST'])
def api_move_source():
    """Move a source to a different cat/region"""
    data=request.get_json(force=True)
    url=data.get('url','')
    new_cat=data.get('cat','').strip()
    new_region=data.get('region','').strip()
    if not url or not new_cat:
        return jsonify({'error':'url and cat required'}),400
    conn=get_db(); cur=conn.cursor()
    # Update in sources_custom (dynamic sources)
    cur.execute("UPDATE sources_custom SET cat=%s, region=%s WHERE url=%s",(new_cat,new_region,url))
    # Update articles already scraped from this source
    cur.execute("UPDATE articles SET cat=%s, region=%s WHERE source_url=%s",(new_cat,new_region,url))
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/api/sources/reorder', methods=['POST'])
def api_reorder_sources():
    """Save drag-drop order for sources"""
    data=request.get_json(force=True)
    orders=data.get('orders',[])  # [{url, sort_order, cat, region}]
    if not orders:
        return jsonify({'ok':True})
    conn=get_db(); cur=conn.cursor()
    for item in orders:
        cur.execute("""INSERT INTO source_order(url,cat,region,sort_order)
            VALUES(%s,%s,%s,%s)
            ON CONFLICT(url) DO UPDATE SET cat=EXCLUDED.cat,region=EXCLUDED.region,sort_order=EXCLUDED.sort_order""",
            (item.get('url'),item.get('cat',''),item.get('region',''),item.get('sort_order',0)))
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/consultant')
def consultant():
    return CONSULTANT_PAGE, 200, {"Content-Type": "text/html; charset=utf-8"}


LANDING_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SubstanCiel</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,400&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --accent:  #1a3c2e;
  --accent2: #1f4a38;
  --accent3: #2a5c46;
  --lime:    #c8e84e;
  --lime2:   #b0d035;
  --lime-bg: rgba(200,232,78,0.10);
  --bg:      #f2f4f0;
  --surface: #ffffff;
  --text:    #111a14;
  --text2:   #3a4a3e;
  --muted:   #7a8e80;
  --border:  #e0e5d8;
  --shadow:  0 2px 8px rgba(26,60,46,0.08);
  --shadow-md: 0 6px 24px rgba(26,60,46,0.11);
  --shadow-lg: 0 16px 48px rgba(26,60,46,0.15);
}

html, body {
  height: 100%;
  font-family: 'DM Sans', system-ui, sans-serif;
  background: var(--accent);
  -webkit-font-smoothing: antialiased;
  overflow: hidden;
}

/* ── PAGE ── */
.page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

/* ── NOISE TEXTURE ── */
.page::before {
  content: '';
  position: absolute; inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.03'/%3E%3C/svg%3E");
  pointer-events: none; z-index: 0;
}

/* ── GLOW BLOBS ── */
.blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.12;
  pointer-events: none;
  z-index: 0;
}
.blob-1 { width: 600px; height: 600px; background: var(--lime); top: -200px; left: 50%; transform: translateX(-50%); animation: float 14s ease-in-out infinite alternate; }
.blob-2 { width: 300px; height: 300px; background: #5adf7a; bottom: 0; left: -60px; animation: float 10s ease-in-out infinite alternate-reverse; }
.blob-3 { width: 200px; height: 200px; background: var(--lime2); bottom: 80px; right: 60px; animation: float 8s ease-in-out infinite alternate; }

@keyframes float { 0% { transform: translateY(0) scale(1); } 100% { transform: translateY(20px) scale(1.05); } }
.blob-1 { animation: floatCenter 14s ease-in-out infinite alternate; }
@keyframes floatCenter { 0% { transform: translateX(-50%) translateY(0); } 100% { transform: translateX(-50%) translateY(24px); } }

/* ── HEADER ── */
header {
  position: relative; z-index: 10;
  display: flex; align-items: center;
  padding: 24px 48px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.logo {
  display: flex; align-items: center; gap: 10px;
}
.logo-mark {
  width: 34px; height: 34px;
  background: var(--lime);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
}
.logo-mark svg { width: 17px; height: 17px; }
.logo-name {
  font-family: 'Syne', sans-serif;
  font-weight: 800; font-size: 17px;
  color: #fff; letter-spacing: -0.3px;
}
.logo-name span { color: var(--lime); }

.header-pill {
  margin-left: auto;
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 10.5px; font-weight: 600;
  color: rgba(200,232,78,0.65);
  letter-spacing: 0.09em; text-transform: uppercase;
  border: 1px solid rgba(200,232,78,0.15);
  padding: 5px 12px; border-radius: 100px;
}
.pulse {
  width: 6px; height: 6px;
  background: var(--lime2); border-radius: 50%;
  animation: pulse 2.2s ease-in-out infinite;
}
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.35;transform:scale(.7)} }

/* ── HERO ── */
.hero {
  flex: 1;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  text-align: center;
  padding: 0 24px 24px;
  position: relative; z-index: 10;
  gap: 0;
}

.hero-eyebrow {
  font-size: 11px; font-weight: 600;
  color: rgba(255,255,255,0.35);
  letter-spacing: 0.12em; text-transform: uppercase;
  margin-bottom: 20px;
}

h1 {
  font-family: 'Syne', sans-serif;
  font-size: clamp(42px, 5.5vw, 68px);
  font-weight: 800;
  color: #fff;
  line-height: 1.0;
  letter-spacing: -2px;
  margin-bottom: 20px;
}
h1 .lime { color: var(--lime); }
h1 .dim  { color: rgba(255,255,255,0.25); font-weight: 700; }

.hero-desc {
  font-size: 15px; font-weight: 300;
  color: rgba(255,255,255,0.4);
  line-height: 1.65;
  max-width: 420px;
  margin-bottom: 44px;
}

/* ── CARDS ── */
.cards {
  display: flex; gap: 14px;
  width: 100%; max-width: 640px;
}

.card {
  flex: 1;
  text-decoration: none;
  border-radius: 18px;
  padding: 24px 26px;
  display: flex; flex-direction: column;
  transition: transform 0.22s cubic-bezier(0.16,1,0.3,1), box-shadow 0.22s;
  position: relative; overflow: hidden;
}
.card:hover { transform: translateY(-4px); }

.card-primary {
  background: var(--lime);
}
.card-primary:hover {
  box-shadow: 0 18px 48px rgba(200,232,78,0.25);
}

.card-secondary {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.10);
  backdrop-filter: blur(12px);
}
.card-secondary:hover {
  background: rgba(255,255,255,0.10);
  border-color: rgba(255,255,255,0.18);
  box-shadow: 0 18px 48px rgba(0,0,0,0.2);
}

.card-header {
  display: flex; align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.card-icon {
  width: 38px; height: 38px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 17px;
}
.card-primary .card-icon { background: rgba(26,60,46,0.12); }
.card-secondary .card-icon { background: rgba(255,255,255,0.08); }

.card-arrow {
  font-size: 20px;
  transition: transform 0.2s;
}
.card-primary .card-arrow { color: var(--accent); }
.card-secondary .card-arrow { color: rgba(255,255,255,0.4); }
.card:hover .card-arrow { transform: translate(3px,-3px); }

.card-title {
  font-family: 'Syne', sans-serif;
  font-size: 16px; font-weight: 800;
  letter-spacing: -0.3px;
  margin-bottom: 6px;
}
.card-primary .card-title { color: var(--accent); }
.card-secondary .card-title { color: #fff; }

.card-desc {
  font-size: 12px; line-height: 1.55;
}
.card-primary .card-desc { color: rgba(26,60,46,0.6); }
.card-secondary .card-desc { color: rgba(255,255,255,0.38); }

.card-tags {
  display: flex; flex-wrap: wrap; gap: 5px;
  margin-top: 16px;
}
.tag {
  font-size: 9.5px; font-weight: 700;
  padding: 3px 8px; border-radius: 100px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
.card-primary .tag { background: rgba(26,60,46,0.1); color: var(--accent); }
.card-secondary .tag { background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.45); border: 1px solid rgba(255,255,255,0.08); }

/* ── FOOTER ── */
footer {
  position: relative; z-index: 10;
  text-align: center;
  padding: 16px;
  font-size: 10.5px; color: rgba(255,255,255,0.18);
  letter-spacing: 0.06em;
}

@media (max-width: 600px) {
  header { padding: 18px 24px; }
  h1 { font-size: 36px; letter-spacing: -1px; }
  .cards { flex-direction: column; max-width: 380px; }
  html, body { overflow: auto; }
  .page { height: auto; min-height: 100vh; }
}
</style>
</head>
<body>
<div class="page">

  <div class="blob blob-1"></div>
  <div class="blob blob-2"></div>
  <div class="blob blob-3"></div>

  <!-- HEADER -->
  <header>
    <div class="logo">
      <div class="logo-mark">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M12 2L3 7v5c0 4.97 3.8 9.63 9 10.93C17.2 21.63 21 16.97 21 12V7L12 2z" fill="#1a3c2e"/>
          <path d="M8.5 12l2.5 2.5 4.5-5" stroke="#c8e84e" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div class="logo-name">Substan<span>Ciel</span></div>
    </div>
    <div class="header-pill">
      <span class="pulse"></span>
      Veille active
    </div>
  </header>

  <!-- HERO -->
  <div class="hero">
    <p class="hero-eyebrow">Financement public · Intelligence artificielle</p>

    <h1>
      Les bons financements<br>
      <span class="lime">au bon moment</span><br>
      <span class="dim">pour vos clients</span>
    </h1>

    <p class="hero-desc">
      Agrégation de subventions et appels à projets nationaux et régionaux — qualifiés et structurés par IA pour les consultants en financement.
    </p>

    <!-- CARTES -->
    <div class="cards">

      <a href="/app" class="card card-primary">
        <div class="card-header">
          <div class="card-icon">🔭</div>
          <span class="card-arrow">↗</span>
        </div>
        <div class="card-title">Espace Veille</div>
        <div class="card-desc">Parcourez, filtrez et qualifiez les dispositifs de financement en temps réel.</div>
        <div class="card-tags">
          <span class="tag">Curation IA</span>
          <span class="tag">70+ sources</span>
          <span class="tag">Multi-régions</span>
        </div>
      </a>

      <a href="/consultant" class="card card-secondary">
        <div class="card-header">
          <div class="card-icon">📋</div>
          <span class="card-arrow">↗</span>
        </div>
        <div class="card-title">Espace Collecte</div>
        <div class="card-desc">Collectez et exportez les fiches. Pré-veille 360° et journal par client.</div>
        <div class="card-tags">
          <span class="tag">Pré-veille 360°</span>
          <span class="tag">Export PPTX</span>
          <span class="tag">Journal</span>
        </div>
      </a>

    </div>
  </div>

  <footer>SubstanCiel · Outil interne de veille subventions</footer>

</div>
</body>
</html>
"""


@app.route('/')
def index():
    return LANDING_PAGE, 200, {"Content-Type": "text/html; charset=utf-8"}

@app.route('/app')
def app_page():
    return HTML_PAGE, 200, {"Content-Type": "text/html; charset=utf-8"}

@app.route('/api/ping')
def ping():
    return 'pong', 200

@app.route('/api/scrape', methods=['POST'])
def scrape_now():
    sources_count = len(get_all_sources())
    def run():
        try:
            run_scraper()
        except Exception as e:
            log.error(f"Manual scrape error: {e}")
    threading.Thread(target=run, daemon=True).start()
    return jsonify({'status': 'started', 'sources': sources_count})



# ══════════════════════════════════════════════════════════════════
# AUTO-TAG AGENT
# ══════════════════════════════════════════════════════════════════
AUTO_TAG_PROMPT = """Tu es un agent de curation pour une veille sur les financements et politiques publiques françaises.

Pour chaque article, tu dois :
1. Décider s'il est PERTINENT (dispositif de financement, appel à projets, actualité réglementaire importante) ou NON PERTINENT (généraliste, hors-sujet, trop vague)
2. Si pertinent, attribuer les tags appropriés parmi la liste ci-dessous
3. Toujours commencer par soit "⭐ Dispositif" soit "⭐ Actualité" (jamais les deux)

TAGS DISPONIBLES (utilise uniquement ceux qui s'appliquent vraiment) :
- Type : ⭐ Dispositif, ⭐ Actualité
- QUI : Association, Collectivité, Entreprise, PME, TPE, ETI, GE, Start-up, Salariés, Jeunesse, ESS/Insertion, DRH
- QUOI : Agriculture, Industrie, Numérique, Énergie/Décarbonation, Tourisme, Culture, Sport, Logement/Bâtiment, Mobilité
- QUE : Transition écologique/énergétique, Biodiversité, Innovation, Inclusion sociale, Emploi/Formation, Entrepreneuriat, Développement économique/territorial
- OÙ : National, Europe, (région si précisée)
- COMMENT : AAP, AMI, AO, Subvention, Prêt, Crédit d'impôt, France 2030, ADEME, Bpifrance, Banque des territoires

RÈGLES :
- Si NON PERTINENT : réponds uniquement {"pertinent": false}
- Si PERTINENT : réponds {"pertinent": true, "tags": ["⭐ Dispositif", "tag2", ...]}
- Maximum 8 tags par article
- Réponds UNIQUEMENT en JSON valide, sans commentaire"""

_autotag_job = {'status': 'idle', 'progress': 0, 'total': 0, 'done': 0, 'tagged': 0, 'deleted': 0, 'errors': 0}
_autotag_lock = threading.Lock()

def _run_autotag(article_ids, delete_irrelevant):
    """
    Curation IA économe — 3 niveaux de traitement :
    1. Article avec CDC (pdf_url) → appel Claude (signal fort = dispositif)
    2. Titre contient mot-clé fort → appel Claude (probable dispositif)
    3. Aucun signal → tag heuristique "⭐ Actualité" sans appel API
    Objectif : minimiser les appels Claude tout en curant les contenus à valeur.
    """
    global _autotag_job
    with _autotag_lock:
        _autotag_job.update({'status':'running','progress':0,'total':len(article_ids),
                             'done':0,'tagged':0,'skipped':0,'errors':0})

    # Mots-clés forts = signal dispositif
    KEYWORDS_FORT = [
        'appel à projets', 'appel a projets', "appel d'offres", 'appel d offres',
        'aap', 'ami ', 'appel à manifestation', 'appel a manifestation',
        'subvention', 'dispositif', 'financement', 'aide aux', 'aides aux',
        'feder', 'fse', 'france 2030', 'bpifrance', 'ademe',
        'banque des territoires', 'programme européen', 'programme europeen',
        'appel à candidature', 'appel a candidature',
        'ouverture des candidatures', 'dépôt de dossier', 'depot de dossier',
        'guichet ouvert', 'eligib', 'bénéficiaires', 'beneficiaires',
    ]

    def has_strong_signal(title, pdf_url):
        if pdf_url:  # CDC détecté = dispositif quasi-certain
            return True
        t = (title or '').lower()
        return any(kw in t for kw in KEYWORDS_FORT)

    for i, art_id in enumerate(article_ids):
        try:
            conn = get_db(); cur = conn.cursor()
            cur.execute("SELECT title, summary, url, pdf_url FROM articles WHERE id=%s", (art_id,))
            row = cur.fetchone()
            if not row:
                cur.close(); conn.close()
                continue

            title   = row['title'] or ''
            summary = row.get('summary', '') or ''
            url     = row['url'] or ''
            pdf_url = row.get('pdf_url') or ''

            # ── Détection CDC en même temps que le tagging ────────────────
            # Si pas de CDC connu → visiter la page pour en chercher un
            if not pdf_url and url:
                try:
                    found_pdf = _scrape_pdf_url(url)
                    if found_pdf:
                        pdf_url = found_pdf
                        cur.execute("UPDATE articles SET pdf_url=%s WHERE id=%s", (pdf_url, art_id))
                        conn.commit()
                except Exception:
                    pass  # Timeout ou erreur réseau — on continue sans CDC

            if has_strong_signal(title, pdf_url):
                # ── Appel Claude (Haiku = le moins cher) ──────────────────────
                context = f"Titre : {title}\nRésumé : {summary[:300]}\nURL : {url}"
                if pdf_url:
                    context += f"\nCDC/PDF détecté : {pdf_url}"
                payload = json.dumps({
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 200,
                    "system": AUTO_TAG_PROMPT,
                    "messages": [{"role": "user", "content": context}]
                }).encode()
                req = Request("https://api.anthropic.com/v1/messages", data=payload, headers={
                    "Content-Type": "application/json",
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01"
                }, method="POST")
                with urlopen(req, timeout=30) as resp:
                    resp_data = json.loads(resp.read())
                text = resp_data["content"][0]["text"].strip()
                m_json = re.search(r'\{[\s\S]*\}', text)
                result = json.loads(m_json.group() if m_json else text)

                tags = result.get('tags', []) if result.get('pertinent', True) else []
                if tags:
                    cur.execute(
                        "UPDATE articles SET tags=%s WHERE id=%s AND (tags IS NULL OR tags='[]' OR tags='[\"\"]')",
                        (json.dumps(tags), art_id)
                    )
                    conn.commit()
                    with _autotag_lock: _autotag_job['tagged'] += 1
                else:
                    with _autotag_lock: _autotag_job['skipped'] += 1

            else:
                # ── Heuristique sans API : tag Actualité ──────────────────────
                tags = ['⭐ Actualité']
                cur.execute(
                    "UPDATE articles SET tags=%s WHERE id=%s AND (tags IS NULL OR tags='[]' OR tags='[\"\"]')",
                    (json.dumps(tags), art_id)
                )
                conn.commit()
                with _autotag_lock: _autotag_job['tagged'] += 1

            cur.close(); conn.close()

        except Exception as e:
            log.warning(f"AutoTag error art_id={art_id}: {e}")
            with _autotag_lock: _autotag_job['errors'] += 1

        with _autotag_lock:
            _autotag_job['done'] = i + 1
            _autotag_job['progress'] = int((i + 1) / len(article_ids) * 100)

    with _autotag_lock:
        _autotag_job['status'] = 'done'

@app.route('/api/auto-tag', methods=['POST'])
def start_autotag():
    global _autotag_job
    if not ANTHROPIC_API_KEY:
        return jsonify({'error':'ANTHROPIC_API_KEY not configured'}), 500
    with _autotag_lock:
        if _autotag_job['status'] == 'running':
            return jsonify({'status':'already_running'}), 200
    data = request.get_json() or {}
    only_untagged = data.get('only_untagged', True)
    delete_irrelevant = data.get('delete_irrelevant', False)
    limit = min(int(data.get('limit', 50)), 200)
    conn = get_db(); cur = conn.cursor()
    if only_untagged:
        cur.execute("SELECT id FROM articles WHERE tags IS NULL OR tags='[]' OR tags='[\"\"]' ORDER BY scraped_at DESC LIMIT %s", (limit,))
    else:
        cur.execute("SELECT id FROM articles ORDER BY scraped_at DESC LIMIT %s", (limit,))
    ids = [r['id'] for r in cur.fetchall()]
    cur.close(); conn.close()
    if not ids:
        return jsonify({'status':'no_articles'})
    t = threading.Thread(target=_run_autotag, args=(ids, delete_irrelevant), daemon=True)
    t.start()
    return jsonify({'status':'started', 'count': len(ids)})

@app.route('/api/auto-tag/status', methods=['GET'])
def autotag_status():
    with _autotag_lock:
        return jsonify(dict(_autotag_job))

@app.route('/api/collect', methods=['POST'])
def collect_dispositif():
    """Fetch a URL, send to Claude, return structured grid."""
    data = request.get_json()
    url = data.get('url','')
    title = data.get('title','')
    article_id = data.get('id')
    if not url:
        return jsonify({'error':'URL required'}),400
    if not ANTHROPIC_API_KEY:
        return jsonify({'error':'ANTHROPIC_API_KEY not configured'}),500

    page_text = ''
    pdf_url = data.get('pdf_url', '')
    source_used = 'page'

    if article_id and not pdf_url:
        try:
            conn_tmp = get_db(); cur_tmp = conn_tmp.cursor()
            cur_tmp.execute("SELECT pdf_url FROM articles WHERE id=%s", (article_id,))
            row_tmp = cur_tmp.fetchone()
            if row_tmp and row_tmp['pdf_url']:
                pdf_url = row_tmp['pdf_url']
            cur_tmp.close(); conn_tmp.close()
        except Exception:
            pass

    if not pdf_url:
        try:
            pdf_url = _scrape_pdf_url(url)
        except Exception:
            pass

    # Priorite 1 : CDC PDF (timeout 12s)
    if pdf_url and pdf_url.lower().split('?')[0].endswith(('.pdf','.doc','.docx')):
        try:
            req_cdc = Request(pdf_url, headers={'User-Agent':'Mozilla/5.0'})
            with urlopen(req_cdc, timeout=12) as resp_cdc:
                raw_cdc = resp_cdc.read(150000)
            try:
                from io import BytesIO
                from pdfminer.high_level import extract_text as pdf_extract
                page_text = pdf_extract(BytesIO(raw_cdc))[:6000]
                source_used = 'cdc_pdf'
            except Exception:
                page_text = raw_cdc.decode('utf-8', errors='ignore')[:6000]
                source_used = 'cdc_raw'
        except Exception as e:
            log.warning(f"CDC fetch error {pdf_url}: {e}")

    # Priorite 2 : page HTML (timeout 10s) — extraction intelligente du contenu utile
    if not page_text:
        try:
            req_html = Request(url, headers={
                'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Accept-Language':'fr-FR,fr;q=0.9',
            })
            with urlopen(req_html, timeout=10) as resp_html:
                raw_html = resp_html.read(200000).decode('utf-8', errors='ignore')

            # Supprimer scripts, styles, nav, footer (bruit)
            NOISE_PAT = re.compile('<(script|style|nav|header|footer|aside)[^>]*>.*?</(script|style|nav|header|footer|aside)>', re.IGNORECASE|re.DOTALL)
            clean = NOISE_PAT.sub(' ', raw_html)

            # Essayer d'extraire la zone de contenu principal
            CONTENT_PAT = re.compile('<(main|article|section|div)[^>]*(content|main|article|body|dispositif|fiche|detail|description)[^>]*>(.*?)</(main|article|section|div)>', re.IGNORECASE|re.DOTALL)
            main_match = CONTENT_PAT.search(clean)
            if main_match:
                zone = main_match.group(3)
            else:
                zone = clean  # fallback : tout le HTML nettoyé

            # Strip tags restants
            text = re.sub(r'<[^>]+>', ' ', zone)
            text = re.sub(r'\s+', ' ', text).strip()

            # Garder 8000 chars — sauter les 500 premiers (souvent menu/breadcrumb)
            if len(text) > 500:
                text = text[500:]
            page_text = text[:8000]

        except Exception as e:
            log.warning(f"Fetch error {url}: {e}")
            page_text = f"Titre : {title}\nURL : {url}\n(Contenu non accessible)"

    # Call Claude Haiku (timeout 25s)
    try:
        cdc_mention = f"\nCahier des charges : {pdf_url}" if pdf_url else ""
        user_content = f"Analyse ce dispositif et remplis la grille.{cdc_mention}\n\nTitre : {title}\nURL : {url}\n[Source : {source_used}]\n\nContenu :\n{page_text}"
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 2000,
            "system": COLLECT_PROMPT,
            "messages": [{"role":"user","content":user_content}]
        }, ensure_ascii=False).encode('utf-8')
        req = Request("https://api.anthropic.com/v1/messages", data=payload, headers={
            "Content-Type":"application/json; charset=utf-8",
            "x-api-key":ANTHROPIC_API_KEY,
            "anthropic-version":"2023-06-01"
        }, method="POST")
        with urlopen(req, timeout=30) as resp:
            raw_resp = resp.read()
            claude_data = json.loads(raw_resp)
        if claude_data.get('type') == 'error':
            raise Exception(f"Anthropic API error: {claude_data.get('error',{}).get('message','unknown')}")
        text = claude_data["content"][0]["text"].strip()
        m = re.search(r'\{[\s\S]*\}', text)
        result = json.loads(m.group() if m else text)
        result['source_url'] = url
        result['article_id'] = article_id
        if pdf_url:
            result['cdc_url'] = pdf_url
        return jsonify(result)
    except Exception as e:
        import traceback
        log.error(f"Collect Claude error: {e}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}),500




# ═══════════════════════════════════════════════════════════════════════════════
# PACKAGES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/packages', methods=['GET'])
def get_packages():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.name, p.created_at,
               COUNT(d.id) as nb
        FROM packages p
        LEFT JOIN dispositifs d ON d.package_id = p.id
        GROUP BY p.id ORDER BY p.created_at DESC
    """)
    rows = cur.fetchall(); cur.close(); conn.close()
    result = []
    for r in rows:
        result.append({'id': r['id'], 'name': r['name'],
                       'created_at': r['created_at'].isoformat() if r['created_at'] else '',
                       'nb': r['nb']})
    return jsonify(result)

@app.route('/api/packages', methods=['POST'])
def create_package():
    data = request.get_json()
    name = data.get('name','').strip()
    if not name:
        return jsonify({'error': 'Nom requis'}), 400
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO packages (name) VALUES (%s) RETURNING id", (name,))
    pkg_id = cur.fetchone()['id']
    conn.commit(); cur.close(); conn.close()
    return jsonify({'id': pkg_id, 'name': name})

@app.route('/api/packages/<int:pid>', methods=['DELETE'])
def delete_package(pid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM packages WHERE id=%s", (pid,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({'status': 'deleted'})

@app.route('/api/packages/<int:pid>/dispositifs', methods=['GET'])
def get_package_dispositifs(pid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM dispositifs WHERE package_id=%s ORDER BY id ASC", (pid,))
    rows = cur.fetchall(); cur.close(); conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d.get('collected_at'): d['collected_at'] = d['collected_at'].isoformat()
        result.append(d)
    return jsonify(result)



@app.route('/api/packages/merge', methods=['POST'])
def merge_packages():
    """Merge two packages into a new one."""
    data = request.get_json()
    pkg_a = data.get('pkg_a')  # source package (current)
    pkg_b = data.get('pkg_b')  # target package to merge with
    new_name = data.get('name', '').strip()
    if not pkg_a or not pkg_b or not new_name:
        return jsonify({'error': 'Paramètres manquants'}), 400
    if pkg_a == pkg_b:
        return jsonify({'error': 'Impossible de fusionner un package avec lui-même'}), 400

    conn = get_db(); cur = conn.cursor()
    # Create new package
    cur.execute("INSERT INTO packages (name) VALUES (%s) RETURNING id", (new_name,))
    new_id = cur.fetchone()['id']
    # Move all dispositifs from A and B into new package (deduplicate by source_url)
    cur.execute("""
        INSERT INTO dispositifs (guichet_financeur, guichet_instructeur, titre, nature,
            beneficiaire, type_depot, date_fermeture, objectif, types_depenses,
            operations_eligibles, depenses_eligibles, criteres_eligibilite,
            depenses_ineligibles, montants_taux, thematiques, territoire,
            points_vigilance, contact, programme_europeen, source_url, cdc_url, package_id)
        SELECT DISTINCT ON (COALESCE(source_url, gen_random_uuid()::text))
            guichet_financeur, guichet_instructeur, titre, nature,
            beneficiaire, type_depot, date_fermeture, objectif, types_depenses,
            operations_eligibles, depenses_eligibles, criteres_eligibilite,
            depenses_ineligibles, montants_taux, thematiques, territoire,
            points_vigilance, contact, programme_europeen, source_url, cdc_url, %s
        FROM dispositifs
        WHERE package_id IN (%s, %s)
        ORDER BY id ASC, COALESCE(source_url, gen_random_uuid()::text), collected_at DESC
    """, (new_id, pkg_a, pkg_b))
    # Delete source packages (dispositifs cascade to SET NULL, already moved)
    cur.execute("DELETE FROM dispositifs WHERE package_id IN (%s, %s)", (pkg_a, pkg_b))
    cur.execute("DELETE FROM packages WHERE id IN (%s, %s)", (pkg_a, pkg_b))
    conn.commit(); cur.close(); conn.close()
    return jsonify({'status': 'merged', 'new_id': new_id, 'name': new_name})


@app.route('/api/packages/<int:pid>/logs', methods=['GET'])
def get_package_logs(pid):
    """Return error logs from batch jobs linked to this package."""
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        SELECT job_id, created_at, total, done, results
        FROM batch_jobs
        WHERE pkg_id = %s
        ORDER BY created_at DESC
        LIMIT 10
    """, (pid,))
    rows = cur.fetchall(); cur.close(); conn.close()
    logs = []
    for r in rows:
        results = r['results'] or []
        if isinstance(results, str):
            import json as _json
            results = _json.loads(results)
        errors = [x for x in results if x.get('status') == 'error']
        logs.append({
            'job_id': r['job_id'],
            'created_at': r['created_at'].isoformat() if r['created_at'] else '',
            'total': r['total'],
            'done': r['done'],
            'errors': errors
        })
    return jsonify(logs)

@app.route('/api/packages/<int:pid>/export-cdc', methods=['GET'])
def export_package_cdc(pid):
    """Download all CDC documents for a package as a ZIP."""
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT name FROM packages WHERE id=%s", (pid,))
    pkg = cur.fetchone()
    if not pkg:
        return jsonify({'error': 'Package introuvable'}), 404
    cur.execute("SELECT titre, source_url, cdc_url FROM dispositifs WHERE package_id=%s AND cdc_url IS NOT NULL AND cdc_url != ''", (pid,))
    rows = cur.fetchall(); cur.close(); conn.close()
    if not rows:
        return jsonify({'error': 'Aucun CDC trouvé dans ce package'}), 404

    import zipfile, io as _io
    from urllib.request import Request as _Req, urlopen as _open
    buf = _io.BytesIO()
    added = 0
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for r in rows:
            titre = (r['titre'] or 'dispositif').replace('/', '-').replace('\\', '-')[:50]
            cdc_url = r['cdc_url']
            try:
                ext = cdc_url.split('?')[0].rsplit('.', 1)[-1].lower()
                if ext not in ('pdf', 'doc', 'docx', 'odt'):
                    ext = 'pdf'
                req = _Req(cdc_url, headers={'User-Agent': 'Mozilla/5.0'})
                with _open(req, timeout=15) as resp:
                    data = resp.read(10_000_000)  # 10 Mo max
                safe_name = f"{added+1:02d}_{titre}.{ext}"
                zf.writestr(safe_name, data)
                added += 1
            except Exception as e:
                log.warning(f"CDC download error {cdc_url}: {e}")
                continue

    if added == 0:
        return jsonify({'error': 'Impossible de télécharger les CDCs'}), 500

    buf.seek(0)
    from flask import send_file
    safe_pkg = pkg['name'].replace(' ', '_').replace('/', '-')[:40]
    return send_file(buf, mimetype='application/zip',
                     as_attachment=True,
                     download_name=f"CDCs_{safe_pkg}.zip")

@app.route('/api/packages/<int:pid>/export-pptx', methods=['GET'])
def export_package_pptx(pid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT name FROM packages WHERE id=%s", (pid,))
    pkg = cur.fetchone()
    if not pkg:
        return jsonify({'error': 'Package introuvable'}), 404
    cur.execute("SELECT * FROM dispositifs WHERE package_id=%s ORDER BY id ASC", (pid,))
    rows = cur.fetchall(); cur.close(); conn.close()
    if not rows:
        return jsonify({'error': 'Package vide'}), 400

    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    import io, base64 as b64mod

    import copy

    def _merge_slide_into_prs(src_slide, dst_prs):
        """Copy a slide including its images into dst_prs."""
        layout = dst_prs.slide_layouts[5]
        new_slide = dst_prs.slides.add_slide(layout)

        # Copy image parts using get_or_add_image_part (returns (ImagePart, rId))
        rId_map = {}
        for rel in src_slide.part.rels.values():
            if 'image' in rel.reltype:
                try:
                    src_img = rel.target_part
                    _img_part, new_rId = new_slide.part.get_or_add_image_part(
                        io.BytesIO(src_img.blob)
                    )
                    rId_map[rel.rId] = new_rId
                except Exception as e:
                    log.warning(f"Image copy error rId={rel.rId}: {e}")

        # Copy spTree with rId remapping for images
        src_sp_tree = src_slide.shapes._spTree
        dst_sp_tree = new_slide.shapes._spTree

        # Clear destination placeholders (keep first 2 mandatory group nodes)
        while len(dst_sp_tree) > 2:
            dst_sp_tree.remove(dst_sp_tree[-1])

        # Deep-copy each child, remapping r:embed / r:link attributes
        for child in list(src_sp_tree)[2:]:
            el = copy.deepcopy(child)
            for node in el.iter():
                for attr in list(node.attrib.keys()):
                    if attr.endswith('}embed') or attr.endswith('}link'):
                        old_rId = node.attrib[attr]
                        if old_rId in rId_map:
                            node.attrib[attr] = rId_map[old_rId]
            dst_sp_tree.append(el)

    # Generate all individual PPTX bytes
    all_pptx = []
    for r in rows:
        data = dict(r)
        if data.get('collected_at'): data['collected_at'] = data['collected_at'].isoformat()
        try:
            pptx_bytes = generate_dispositif_pptx(data)
            all_pptx.append(pptx_bytes)
        except Exception as e:
            log.warning(f"Package PPTX generate error: {e}")
            continue

    if not all_pptx:
        return jsonify({'error': 'Aucune slide generee'}), 500

    # Use first pptx as base, merge all others into it
    base_prs = Presentation(io.BytesIO(all_pptx[0]))

    for pptx_bytes in all_pptx[1:]:
        try:
            src_prs = Presentation(io.BytesIO(pptx_bytes))
            for slide in src_prs.slides:
                _merge_slide_into_prs(slide, base_prs)
        except Exception as e:
            log.warning(f"Package PPTX merge error: {e}")
            continue

    combined_prs = base_prs

    buf = io.BytesIO()
    combined_prs.save(buf)
    buf.seek(0)
    from flask import send_file
    safe_name = pkg['name'].replace(' ', '_').replace('/', '-')[:40]
    return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
                     as_attachment=True, download_name=f"Package_{safe_name}.pptx")


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH COLLECT (Excel upload)
# ═══════════════════════════════════════════════════════════════════════════════


# ── Batch collect state (DB-backed, multi-worker safe) ───────────────────────
def _job_update(job_id, done=None, result=None, status=None):
    """Atomically update a batch job in DB."""
    try:
        conn = get_db(); cur = conn.cursor()
        if result is not None:
            cur.execute(
                "UPDATE batch_jobs SET done=done+1, results=results||%s::jsonb WHERE job_id=%s",
                (json.dumps([result]), job_id)
            )
        if status:
            cur.execute("UPDATE batch_jobs SET status=%s WHERE job_id=%s", (status, job_id))
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        log.error(f"job_update error: {e}")

def _job_get(job_id):
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT * FROM batch_jobs WHERE job_id=%s", (job_id,))
        row = cur.fetchone(); cur.close(); conn.close()
        if not row: return None
        return dict(row)
    except Exception:
        return None

def _job_create(job_id, total, pkg_id, pkg_name):
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO batch_jobs (job_id, status, total, done, pkg_id, pkg_name, results) VALUES (%s,'running',%s,0,%s,%s,'[]')",
            (job_id, total, pkg_id, pkg_name)
        )
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        log.error(f"job_create error: {e}")



@app.route('/api/collect-text', methods=['POST'])
def collect_text():
    """Analyze raw pasted text content with Claude."""
    if not ANTHROPIC_API_KEY:
        return jsonify({'error': 'ANTHROPIC_API_KEY not configured'}), 500
    data = request.get_json()
    text = (data.get('text') or '').strip()
    source_url = (data.get('source_url') or '').strip()
    if not text:
        return jsonify({'error': 'Contenu vide'}), 400
    try:
        url_mention = f"\nURL source : {source_url}" if source_url else ""
        user_content = f"Analyse ce contenu et remplis la grille.{url_mention}\n[Source : scrape_manuel]\n\nContenu :\n{text[:8000]}"
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 2000,
            "system": COLLECT_PROMPT,
            "messages": [{"role": "user", "content": user_content}]
        }).encode()
        req = Request("https://api.anthropic.com/v1/messages", data=payload, headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        }, method="POST")
        with urlopen(req, timeout=30) as resp:
            claude_data = json.loads(resp.read())
        txt = claude_data["content"][0]["text"].strip()
        m = re.search(r'\{[\s\S]*\}', txt)
        result = json.loads(m.group() if m else txt)
        result['source_url'] = source_url or ''
        return jsonify(result)
    except Exception as e:
        log.error(f"collect_text error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/collect-cdc', methods=['POST'])
def collect_cdc():
    """Analyze an uploaded CDC file (PDF/Word) directly with Claude."""
    if not ANTHROPIC_API_KEY:
        return jsonify({'error': 'ANTHROPIC_API_KEY not configured'}), 500

    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'Fichier manquant'}), 400

    source_url = request.form.get('source_url', '').strip()
    filename = file.filename.lower()

    page_text = ''
    source_used = 'cdc_upload'

    try:
        raw = file.read(200000)
        if filename.endswith('.pdf'):
            try:
                from io import BytesIO
                from pdfminer.high_level import extract_text as pdf_extract
                page_text = pdf_extract(BytesIO(raw))[:8000]
            except Exception:
                page_text = raw.decode('utf-8', errors='ignore')[:8000]
        else:
            # Word doc - try docx
            try:
                import zipfile, io as _io
                with zipfile.ZipFile(_io.BytesIO(raw)) as z:
                    if 'word/document.xml' in z.namelist():
                        xml = z.read('word/document.xml').decode('utf-8', errors='ignore')
                        import re as _re
                        page_text = _re.sub(r'<[^>]+>', ' ', xml)
                        page_text = _re.sub(r'\s+', ' ', page_text).strip()[:8000]
            except Exception:
                page_text = raw.decode('utf-8', errors='ignore')[:8000]
    except Exception as e:
        return jsonify({'error': f'Lecture fichier impossible : {e}'}), 400

    if not page_text.strip():
        return jsonify({'error': 'Impossible d extraire le texte du document'}), 400

    try:
        url_mention = f"\nURL source : {source_url}" if source_url else ""
        user_content = f"Analyse ce cahier des charges et remplis la grille.{url_mention}\n[Source : {source_used}]\n\nContenu :\n{page_text}"
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 2000,
            "system": COLLECT_PROMPT,
            "messages": [{"role": "user", "content": user_content}]
        }).encode()
        req = Request("https://api.anthropic.com/v1/messages", data=payload, headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        }, method="POST")
        with urlopen(req, timeout=30) as resp:
            claude_data = json.loads(resp.read())
        text = claude_data["content"][0]["text"].strip()
        m = re.search(r'\{[\s\S]*\}', text)
        result = json.loads(m.group() if m else text)
        result['source_url'] = source_url or ''
        result['cdc_uploaded'] = True
        return jsonify(result)
    except Exception as e:
        log.error(f"CDC collect error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/collect-batch', methods=['POST'])
def collect_batch():
    """Start async batch collect. Returns job_id immediately."""
    try:
        import openpyxl
    except ImportError:
        return jsonify({'error': 'openpyxl non installe'}), 500

    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'Fichier manquant'}), 400

    package_name = request.form.get('package_name', '').strip()
    create_pkg = request.form.get('create_package', 'false') == 'true' and bool(package_name)

    try:
        import io as _io
        wb = openpyxl.load_workbook(_io.BytesIO(file.read()), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        urls = []
        for row in ws.iter_rows(min_row=1, max_row=31, min_col=1, max_col=1, values_only=True):
            val = row[0]
            if val and isinstance(val, str) and val.strip().startswith('http'):
                urls.append(val.strip())
        wb.close()
    except Exception as e:
        return jsonify({'error': f'Lecture Excel impossible : {e}'}), 400

    if not urls:
        return jsonify({'error': 'Aucune URL trouvee en colonne A'}), 400
    urls = urls[:30]

    # Create package if requested
    pkg_id = None
    if create_pkg:
        conn = get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO packages (name) VALUES (%s) RETURNING id", (package_name,))
        pkg_id = cur.fetchone()['id']
        conn.commit(); cur.close(); conn.close()

    import uuid
    job_id = str(uuid.uuid4())[:8]
    _job_create(job_id, len(urls), pkg_id, package_name)

    # Run in background thread
    def run_job():
        fields = ['guichet_financeur','guichet_instructeur','titre','nature','beneficiaire',
                  'type_depot','date_fermeture','objectif','types_depenses','operations_eligibles',
                  'depenses_eligibles','criteres_eligibilite','depenses_ineligibles','montants_taux',
                  'thematiques','territoire','points_vigilance','contact','programme_europeen','source_url','cdc_url']
        for idx, url in enumerate(urls):
            result = {'url': url, 'index': idx, 'status': 'error', 'titre': '', 'error': ''}
            try:
                page_text = ''
                pdf_url = None
                source_used = 'page'
                try:
                    pdf_url = _scrape_pdf_url(url)
                except Exception:
                    pass
                if pdf_url and pdf_url.lower().split('?')[0].endswith(('.pdf','.doc','.docx')):
                    try:
                        req_cdc = Request(pdf_url, headers={'User-Agent':'Mozilla/5.0'})
                        with urlopen(req_cdc, timeout=12) as resp_cdc:
                            raw_cdc = resp_cdc.read(150000)
                        try:
                            from io import BytesIO
                            from pdfminer.high_level import extract_text as pdf_extract
                            page_text = pdf_extract(BytesIO(raw_cdc))[:6000]
                            source_used = 'cdc_pdf'
                        except Exception:
                            page_text = raw_cdc.decode('utf-8', errors='ignore')[:6000]
                            source_used = 'cdc_raw'
                    except Exception as e:
                        log.warning(f"Batch CDC error {pdf_url}: {e}")
                if not page_text:
                    try:
                        req_html = Request(url, headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                        with urlopen(req_html, timeout=10) as resp_html:
                            raw_html = resp_html.read(200000).decode('utf-8', errors='ignore')
                        NOISE_PAT = re.compile('<(script|style|nav|header|footer|aside)[^>]*>.*?</(script|style|nav|header|footer|aside)>', re.IGNORECASE|re.DOTALL)
                        clean = NOISE_PAT.sub(' ', raw_html)
                        text = re.sub(r'<[^>]+>', ' ', clean)
                        text = re.sub(r'\s+', ' ', text).strip()
                        page_text = text[500:8500] if len(text) > 500 else text[:8000]
                    except Exception:
                        page_text = f"URL: {url}"
                cdc_mention = f"\nCahier des charges : {pdf_url}" if pdf_url else ""
                user_content = f"Analyse ce dispositif et remplis la grille.{cdc_mention}\nURL : {url}\n[Source : {source_used}]\n\nContenu :\n{page_text}"
                payload = json.dumps({
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 2000,
                    "system": COLLECT_PROMPT,
                    "messages": [{"role":"user","content":user_content}]
                }, ensure_ascii=False).encode('utf-8')
                req = Request("https://api.anthropic.com/v1/messages", data=payload, headers={
                    "Content-Type":"application/json",
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version":"2023-06-01"
                }, method="POST")
                with urlopen(req, timeout=30) as resp:
                    claude_data = json.loads(resp.read())
                text_resp = claude_data["content"][0]["text"].strip()
                m = re.search(r'\{[\s\S]*\}', text_resp)
                disp = json.loads(m.group() if m else text_resp)
                disp['source_url'] = url
                if pdf_url: disp['cdc_url'] = pdf_url
                conn2 = get_db(); cur2 = conn2.cursor()
                # Only block duplicate within the same package (or globally if no package)
                if pkg_id:
                    cur2.execute("SELECT id FROM dispositifs WHERE source_url=%s AND package_id=%s", (url, pkg_id))
                else:
                    cur2.execute("SELECT id FROM dispositifs WHERE source_url=%s AND package_id IS NULL", (url,))
                existing = cur2.fetchone()
                if existing:
                    result['status'] = 'duplicate'
                    result['titre'] = disp.get('titre', url)
                else:
                    cols = ','.join(fields)
                    placeholders = ','.join(['%s']*len(fields))
                    vals = [disp.get(f,'') for f in fields]
                    if pkg_id:
                        cur2.execute(f"INSERT INTO dispositifs ({cols}, package_id) VALUES ({placeholders}, %s) RETURNING id", vals + [pkg_id])
                    else:
                        cur2.execute(f"INSERT INTO dispositifs ({cols}) VALUES ({placeholders}) RETURNING id", vals)
                    conn2.commit()
                    result['status'] = 'saved'
                    result['titre'] = disp.get('titre', url)
                cur2.close(); conn2.close()
            except Exception as e:
                result['error'] = str(e)[:120]
                log.error(f"Batch error {url}: {e}")
            _job_update(job_id, result=result)
        _job_update(job_id, status='done')

    t = threading.Thread(target=run_job, daemon=True)
    t.start()
    return jsonify({'job_id': job_id, 'total': len(urls), 'pkg_id': pkg_id, 'pkg_name': package_name})


@app.route('/api/collect-batch/<job_id>', methods=['GET'])
def collect_batch_status(job_id):
    """Poll batch collect job status."""
    job = _job_get(job_id)
    if not job:
        return jsonify({'error': 'Job introuvable'}), 404
    # Convert DB row to expected format
    results = job.get('results') or []
    if isinstance(results, str):
        results = json.loads(results)
    return jsonify({
        'status': job['status'],
        'total': job['total'],
        'done': job['done'],
        'pkg_id': job['pkg_id'],
        'pkg_name': job['pkg_name'],
        'results': results
    })


@app.route('/api/dispositifs', methods=['GET'])
def get_dispositifs():
    conn = get_db(); cur = conn.cursor()
    # Deduplicate by source_url — keep the most recently collected version per URL
    cur.execute("""
        SELECT DISTINCT ON (COALESCE(source_url, id::text)) *
        FROM dispositifs
        ORDER BY COALESCE(source_url, id::text), collected_at DESC
    """)
    rows = cur.fetchall(); cur.close(); conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d.get('collected_at'): d['collected_at'] = d['collected_at'].isoformat()
        result.append(d)
    return jsonify(result)

@app.route('/api/dispositifs', methods=['POST'])
def save_dispositif():
    data = request.get_json()
    fields = ['guichet_financeur','guichet_instructeur','titre','nature','beneficiaire',
              'type_depot','date_fermeture','objectif','types_depenses','operations_eligibles',
              'depenses_eligibles','criteres_eligibilite','depenses_ineligibles','montants_taux',
              'thematiques','territoire','points_vigilance','contact','programme_europeen','source_url']
    conn = get_db(); cur = conn.cursor()
    cols = ','.join(fields)
    placeholders = ','.join(['%s']*len(fields))
    vals = [data.get(f,'') for f in fields]
    src_url = data.get('source_url','')
    if src_url:
        cur.execute("SELECT id FROM dispositifs WHERE source_url=%s", (src_url,))
        if cur.fetchone():
            cur.close(); conn.close()
            return jsonify({'status':'duplicate','message':'Déjà dans la base'}), 200
    cur.execute(f"INSERT INTO dispositifs ({cols}) VALUES ({placeholders})", vals)
    conn.commit(); cur.close(); conn.close()
    return jsonify({'status':'saved'})


# ═══════════════════════════════════════════════════════════════════════════════
# PDF / CAHIERS DES CHARGES
# ═══════════════════════════════════════════════════════════════════════════════

CDC_DOC_KEYWORDS = [
    'cahier', 'cahier-des-charges', 'reglement', 'regl', 'appel-a-projets',
    'appel_a_projets', 'notice', 'dossier', 'formulaire', 'guide', 'annexe',
    'modalites', 'candidature', 'depot', 'programme', 'cdc', 'specifications'
]
CDC_DOC_EXTENSIONS = ('.pdf', '.doc', '.docx', '.odt', '.xls', '.xlsx')

def _make_absolute(href, page_url):
    """Convert relative href to absolute URL."""
    from urllib.parse import urlparse, urljoin
    if href.startswith('http'):
        return href
    return urljoin(page_url, href)

def _scrape_pdf_url(page_url):
    """Visit a page and find a CDC document link (PDF/Word/image). Returns URL or None."""
    try:
        req = Request(page_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        with urlopen(req, timeout=8) as resp:
            raw = resp.read(400000).decode('utf-8', errors='replace')

        # Extraire tous les liens <a href="...">texte</a>
        links = re.findall(r'<a[^>]+href=["\'\s]?([^"\'\s>]+)["\'\s>][^>]*>(.*?)</a>',
                           raw, re.IGNORECASE | re.DOTALL)

        candidates_url_kw  = []  # href contient extension + mot-clé
        candidates_url_ext = []  # href contient juste extension
        candidates_txt_kw  = []  # texte du lien contient mot-clé

        for href, text in links:
            href = href.strip()
            if not href or href.startswith('#') or href.startswith('mailto'):
                continue
            lower_href = href.lower().split('?')[0]
            text_clean = re.sub(r'<[^>]+>', ' ', text).strip().lower()
            has_ext = any(lower_href.endswith(ext) for ext in CDC_DOC_EXTENSIONS)
            has_kw_url = any(kw in lower_href for kw in CDC_DOC_KEYWORDS)
            has_kw_txt = any(kw in text_clean for kw in CDC_DOC_KEYWORDS)

            abs_href = _make_absolute(href, page_url)
            if not abs_href.startswith('http'):
                continue

            if has_ext and has_kw_url:
                candidates_url_kw.append(abs_href)
            elif has_ext:
                candidates_url_ext.append(abs_href)
            elif has_kw_txt and has_ext:
                # Texte CDC + extension document = candidat valide
                candidates_txt_kw.append(abs_href)
            # Sinon : lien HTML avec texte CDC = ignoré (trop de bruit)

        # Retourne le meilleur candidat par priorité
        # Seuls les liens avec vraie extension document sont retenus
        for pool in [candidates_url_kw, candidates_url_ext, candidates_txt_kw]:
            if pool:
                return pool[0]

    except Exception as e:
        log.warning(f"CDC scrape failed for {page_url}: {e}")
    return None

def _scrape_pdf_url_ai(page_url):
    """Use Claude to find the PDF/CDC link on a page. Returns URL or None."""
    try:
        req = Request(page_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=10) as resp:
            raw = resp.read(100000).decode('utf-8', errors='replace')
        # Strip tags for Claude
        clean = re.sub(r'<[^>]+>', ' ', raw)
        clean = re.sub(r'\s+', ' ', clean)[:6000]

        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 300,
            "messages": [{
                "role": "user",
                "content": f"""Analyse cette page web et trouve l'URL du cahier des charges, règlement, ou document PDF principal (appel à projets, dossier de candidature, notice, etc.).

URL de la page : {page_url}

Contenu de la page (extrait) :
{clean}

Réponds UNIQUEMENT avec l'URL complète du PDF si tu en trouves un. Si tu n'en trouves pas, réponds exactement : AUCUN"""
            }]
        }).encode()

        api_req = Request(
            'https://api.anthropic.com/v1/messages',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01'
            }
        )
        with urlopen(api_req, timeout=30) as resp:
            result = json.loads(resp.read())
        text = result['content'][0]['text'].strip()
        if text and text != 'AUCUN' and text.startswith('http'):
            return text
    except Exception as e:
        log.warning(f"AI PDF search failed: {e}")
    return None

@app.route('/api/articles/fetch-pdf', methods=['POST'])
def fetch_pdf_single():
    """Scraping pour 1 article avec debug détaillé."""
    data = request.json or {}
    article_id = data.get('article_id')
    if not article_id:
        return jsonify({'error': 'article_id required'}), 400
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT url, title FROM articles WHERE id=%s", (article_id,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            return jsonify({'error': 'not found'}), 404
        page_url = row['url']
        doc_url = None
        debug_info = {'page_url': page_url, 'links_found': 0, 'error': None}
        try:
            req = Request(page_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            })
            with urlopen(req, timeout=8) as resp:
                raw = resp.read(400000).decode('utf-8', errors='replace')
            links = re.findall(r'<a[^>]+href=["\'\s]?([^"\'\s>]+)["\'\s>][^>]*>(.*?)</a>',
                               raw, re.IGNORECASE | re.DOTALL)
            debug_info['links_found'] = len(links)
            # Collect all candidates for debug
            all_ext_links = []
            for href, text in links:
                href = href.strip()
                if not href or href.startswith('#') or href.startswith('mailto'):
                    continue
                lower_href = href.lower().split('?')[0]
                if any(lower_href.endswith(ext) for ext in CDC_DOC_EXTENSIONS):
                    abs_href = _make_absolute(href, page_url)
                    text_clean = re.sub(r'<[^>]+>', ' ', text).strip()[:60]
                    all_ext_links.append({'href': abs_href, 'text': text_clean})
            debug_info['ext_links'] = all_ext_links[:10]
            doc_url = _scrape_pdf_url(page_url)
        except Exception as e:
            debug_info['error'] = str(e)
            log.error(f"CDC scrape error #{article_id}: {e}")
        cur.execute("UPDATE articles SET pdf_url=%s WHERE id=%s", (doc_url, article_id))
        conn.commit(); cur.close(); conn.close()
        log.info(f"CDC #{article_id}: {doc_url} | debug={debug_info}")
        return jsonify({'article_id': article_id, 'pdf_url': doc_url, 'doc_url': doc_url,
                        'title': row['title'], 'debug': debug_info})
    except Exception as e:
        log.error(f"CDC route error: {e}")
        return jsonify({'error': str(e), 'pdf_url': None, 'doc_url': None}), 200

# ── CDC scan job state ──────────────────────────────────────────────────────
_cdc_job = {'status': 'idle', 'done': 0, 'total': 0, 'results': [], 'error': None}
_cdc_lock = threading.Lock()

def _run_cdc_scan_bg(article_ids, use_ai=False):
    """Background thread : scan CDC sans bloquer Gunicorn."""
    from concurrent.futures import ThreadPoolExecutor, as_completed as fut_completed
    global _cdc_job
    with _cdc_lock:
        _cdc_job = {'status': 'running', 'done': 0, 'total': len(article_ids), 'results': [], 'error': None}

    conn = get_db(); cur = conn.cursor()
    try:
        articles = []
        for aid in article_ids:
            cur.execute("SELECT id, url, title, pdf_url FROM articles WHERE id=%s", (aid,))
            row = cur.fetchone()
            if row:
                articles.append(dict(row))

        def scan_one(art):
            try:
                if use_ai:
                    doc_url = art['pdf_url'] or _scrape_pdf_url_ai(art['url'])
                else:
                    doc_url = _scrape_pdf_url(art['url'])
                return {'article_id': art['id'], 'doc_url': doc_url, 'title': art['title'], 'source': 'ai' if use_ai else 'scan'}
            except Exception as e:
                return {'article_id': art['id'], 'doc_url': None, 'title': art.get('title',''), 'source': 'error'}

        results = []
        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = {ex.submit(scan_one, a): a for a in articles}
            for fut in fut_completed(futures):
                r = fut.result()
                results.append(r)
                # Save to DB immediately
                try:
                    cur.execute("UPDATE articles SET pdf_url=%s WHERE id=%s", (r['doc_url'], r['article_id']))
                    conn.commit()
                except Exception:
                    conn.rollback()
                with _cdc_lock:
                    _cdc_job['done'] += 1
                    _cdc_job['results'].append(r)

        with _cdc_lock:
            _cdc_job['status'] = 'done'
    except Exception as e:
        with _cdc_lock:
            _cdc_job['status'] = 'error'
            _cdc_job['error'] = str(e)
        log.error(f"CDC scan error: {e}")
    finally:
        cur.close(); conn.close()

@app.route('/api/articles/fetch-pdf-batch', methods=['POST'])
def fetch_pdf_batch():
    """Lance un scan CDC en arrière-plan et retourne immédiatement."""
    global _cdc_job
    with _cdc_lock:
        if _cdc_job['status'] == 'running':
            return jsonify({'status': 'already_running', 'done': _cdc_job['done'], 'total': _cdc_job['total']}), 200

    data = request.json or {}
    ids = data.get('article_ids', [])
    if not ids:
        return jsonify({'error': 'article_ids required'}), 400

    ids = ids[:200]  # max 200 articles
    t = threading.Thread(target=_run_cdc_scan_bg, args=(ids, False), daemon=True)
    t.start()
    return jsonify({'status': 'started', 'total': len(ids)})

@app.route('/api/articles/fetch-pdf-status', methods=['GET'])
def fetch_pdf_status():
    """Polling : retourne l'état du scan CDC en cours."""
    with _cdc_lock:
        job = dict(_cdc_job)
    return jsonify(job)

@app.route('/api/articles/fetch-pdf-ai', methods=['POST'])
def fetch_pdf_ai():
    """Lance un scan IA CDC en arrière-plan."""
    global _cdc_job
    if not ANTHROPIC_API_KEY:
        return jsonify({'error': 'API key not configured'}), 500
    with _cdc_lock:
        if _cdc_job['status'] == 'running':
            return jsonify({'status': 'already_running'}), 200
    data = request.json or {}
    ids = data.get('article_ids', [])
    if not ids:
        return jsonify({'error': 'article_ids required'}), 400
    ids = ids[:30]  # max 30 pour l'IA (coût)
    t = threading.Thread(target=_run_cdc_scan_bg, args=(ids, True), daemon=True)
    t.start()
    return jsonify({'status': 'started', 'total': len(ids)})

@app.route('/api/dispositifs/<int:did>', methods=['DELETE'])
def delete_dispositif(did):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM dispositifs WHERE id=%s",(did,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({'status':'deleted'})

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_scraper,'interval',hours=6)
    scheduler.start()
    log.info("Scheduler started")

if __name__ == '__main__':
    try:
        init_db()
    except Exception as e:
        log.error(f"ERREUR init_db: {e}")
    try:
        start_scheduler()
    except Exception as e:
        log.error(f"ERREUR scheduler: {e}")
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)))
else:
    try:
        init_db()
        log.info("DB initialisée avec succès")
    except Exception as e:
        log.error(f"ERREUR init_db: {e}")
        log.error("Le site démarrera mais la DB est inaccessible — vérifiez DATABASE_URL et Supabase")
    try:
        start_scheduler()
    except Exception as e:
        log.error(f"ERREUR scheduler: {e}")
