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
Ta mission est d'analyser le contenu d'une page web et d'en extraire une grille structurée.

GRILLE À REMPLIR (19 champs obligatoires) :
- Guichet financeur : l'organisme qui finance
- Guichet instructeur : l'organisme qui instruit le dossier
- Titre : nom exact du dispositif
- Nature : catégorie parmi [Subvention, Prêt, Avance remboursable, Garantie, Crédit d'impôt, Investissement en fonds propres, Aide en nature, Exonération fiscale]
- Bénéficiaire : parmi [Entreprise, PME, TPE, ETI, GE, Start-up, Association, Collectivité, Agriculteur, Particulier, Chercheur, ESS]
- Type de dépôt : modalités de dépôt du dossier
- Date de fermeture : date limite de candidature
- Objectif : objectif principal du dispositif (concis)
- Types de dépenses : uniquement parmi [Investissement, Fonctionnement, Étude]
- Opérations éligibles : actions/projets financés (concis)
- Dépenses éligibles : postes de dépenses couverts (concis)
- Critères d'éligibilité : conditions requises (concis)
- Dépenses inéligibles : ce qui est exclu
- Montants et taux d'aide : montants min/max, taux de couverture
- Thématiques : sujets couverts
- Territoire concerné : zone géographique
- Points de vigilance : points d'attention importants
- Contact : coordonnées de contact
- Programme européen : uniquement si explicitement mentionné

RÈGLES STRICTES :
- Toute information absente = "Information non fournie"
- Aucune déduction ni hypothèse
- Réponse UNIQUEMENT en JSON valide avec ces clés exactes :
guichet_financeur, guichet_instructeur, titre, nature, beneficiaire, type_depot,
date_fermeture, objectif, types_depenses, operations_eligibles, depenses_eligibles,
criteres_eligibilite, depenses_ineligibles, montants_taux, thematiques, territoire,
points_vigilance, contact, programme_europeen"""


TEMPLATE_B64 = "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AQBwcHQvc2xpZGVMYXlvdXRzL19yZWxzL3NsaWRlTGF5b3V0NC54bWwucmVsc1BLAQIUAxQAAAAIAHGHalyyVKtsqAAAACQBAAAsAAAAAAAAAAAAAACkgXqaAQBwcHQvc2xpZGVMYXlvdXRzL19yZWxzL3NsaWRlTGF5b3V0MS54bWwucmVsc1BLAQIUAxQAAAAIAHGHalyyVKtsqAAAACQBAAAsAAAAAAAAAAAAAACkgWybAQBwcHQvc2xpZGVMYXlvdXRzL19yZWxzL3NsaWRlTGF5b3V0OS54bWwucmVsc1BLAQIUAxQAAAAIAHGHalyyVKtsqAAAACQBAAAsAAAAAAAAAAAAAACkgV6cAQBwcHQvc2xpZGVMYXlvdXRzL19yZWxzL3NsaWRlTGF5b3V0OC54bWwucmVsc1BLAQIUAxQAAAAIAHGHalziIe1ruwAAAKwBAAAqAAAAAAAAAAAAAACkgVCdAQBwcHQvbm90ZXNTbGlkZXMvX3JlbHMvbm90ZXNTbGlkZTIueG1sLnJlbHNQSwECFAMUAAAACABxh2pcMXgB/LoAAACsAQAAKgAAAAAAAAAAAAAApIFTngEAcHB0L25vdGVzU2xpZGVzL19yZWxzL25vdGVzU2xpZGUxLnhtbC5yZWxzUEsBAhQDFAAAAAgAcYdqXNPqF97rAAAA2AMAACAAAAAAAAAAAAAAAKSBVZ8BAHBwdC9zbGlkZXMvX3JlbHMvc2xpZGUxLnhtbC5yZWxzUEsBAhQDFAAAAAgAcYdqXOoTnyXqAAAA2AMAACAAAAAAAAAAAAAAAKSBfqABAHBwdC9zbGlkZXMvX3JlbHMvc2xpZGUyLnhtbC5yZWxzUEsBAhQDFAAAAAgAcYdqXA8jHfAEAQAAUAgAACwAAAAAAAAAAAAAAKSBpqEBAHBwdC9zbGlkZU1hc3RlcnMvX3JlbHMvc2xpZGVNYXN0ZXIxLnhtbC5yZWxzUEsBAhQDFAAAAAgAcYdqXMjlIEmkAAAAEQEAACwAAAAAAAAAAAAAAKSB9KIBAHBwdC9ub3Rlc01hc3RlcnMvX3JlbHMvbm90ZXNNYXN0ZXIxLnhtbC5yZWxzUEsFBgAAAAA0ADQAxg8AAOKjAQAAAA=="

def generate_dispositif_pptx(data):
    """Generate 2-slide PPTX from embedded template (v3 — logo + fixed title)."""
    import re, urllib.request as ureq
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
        n = len(t)
        if n <= 35:  return Pt(24)
        if n <= 50:  return Pt(20)
        if n <= 70:  return Pt(17)
        return Pt(14)

    # ── Logo fetch : Google Favicons (sz=128) ────────────────────────────────
    KNOWN_DOMAINS = {
        'ademe': 'ademe.fr',
        'bpifrance': 'bpifrance.fr',
        'anah': 'anah.fr',
        'anct': 'anct.gouv.fr',
        'cerema': 'cerema.fr',
        'banque des territoires': 'banquedesterritoires.fr',
        'france 2030': 'gouvernement.fr',
        'dreal': 'ecologie.gouv.fr',
        'dreets': 'travail.gouv.fr',
        'direccte': 'travail.gouv.fr',
        'carsat': 'carsat.fr',
        'urssaf': 'urssaf.fr',
        'msa': 'msa.fr',
        'caisse des depots': 'caissedesdepots.fr',
        'feder': 'europe-en-france.gouv.fr',
        'region': None,
        'departement': None,
        'conseil': None,
    }

    def guess_domain(name):
        nl = name.lower()
        for key, domain in KNOWN_DOMAINS.items():
            if key in nl and domain:
                return domain
        # Build a simple domain from first significant word
        words = re.sub(r'[^a-z0-9 ]', '', nl).split()
        stop = {'de', 'du', 'des', 'le', 'la', 'les', 'et', 'en', 'au', 'aux',
                'ile', 'region', 'grand', 'conseil', 'departement', 'direction',
                'service', 'agence'}
        sig = [w for w in words if w not in stop and len(w) > 2]
        if sig:
            return sig[0] + '.fr'
        return None

    def fetch_logo_bytes(guichet_name):
        """Return (image_bytes, extension) or (None, None)."""
        domain = guess_domain(guichet_name)
        if not domain:
            return None, None
        # Try Google Favicons at 128px
        url = f'https://www.google.com/s2/favicons?domain={domain}&sz=128'
        try:
            req = ureq.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with ureq.urlopen(req, timeout=5) as resp:
                raw = resp.read()
                ct = resp.headers.get('content-type', '')
                # Google returns a 16x16 grey fallback for unknown domains — it's ~524 bytes
                if len(raw) < 800:
                    return None, None
                ext = 'png' if 'png' in ct else 'jpeg'
                return raw, ext
        except Exception:
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
            depot_txt = safe(data.get('type_depot'))
            fc = safe(data.get('date_fermeture'))
            if fc and fc != '—':
                depot_txt += f' — Clôture : {fc}'
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

        elif sid == 14:
            set_second_para(shape, safe(data.get('beneficiaire')))

        elif sid == 15:
            set_second_para(shape, safe(data.get('montants_taux')))

        elif sid == 16:
            set_second_para(shape, safe(data.get('points_vigilance')))

        elif sid == 5:
            # Logo zone slide 2
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
.sort-row {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 14px;
}
.sort-label { font-size: 11px; color: var(--muted); }
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
.articles-list { display: flex; flex-direction: column; gap: 10px; }

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

.article-card-top {
  display: flex; align-items: flex-start; gap: 12px; margin-bottom: 8px;
}
.article-card-source {
  font-size: 10px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.07em; color: var(--muted);
  white-space: nowrap; margin-top: 2px;
}
.article-card-title {
  font-family: 'Syne', sans-serif; font-weight: 700; font-size: 14px;
  line-height: 1.35; color: var(--text); flex: 1;
}
.article-card-date {
  font-size: 10px; color: var(--muted); white-space: nowrap; margin-top: 2px;
}
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
.disp-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }

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
  <div class="header-tag">Espace Consultants</div>
  <nav class="header-tabs">
    <button class="header-tab active" onclick="switchTab('veille', this)">📰 Veille</button>
    <button class="header-tab" onclick="switchTab('dispositifs', this)">🗄 Dispositifs</button>
    <button class="header-tab" onclick="switchTab('cdc', this)">📋 Cahiers des charges</button>
    <button class="header-tab" onclick="switchTab('veille360', this)">🔍 Pré-veille 360°</button>
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
      <div class="stat-chip"><div class="stat-chip-val" id="st-articles">—</div><div class="stat-chip-lbl">Articles</div></div>
      <div class="stat-chip"><div class="stat-chip-val" id="st-dispositifs">—</div><div class="stat-chip-lbl">Dispositifs</div></div>
      <div class="stat-chip"><div class="stat-chip-val" id="st-cdc">—</div><div class="stat-chip-lbl">Cahiers</div></div>
      <div class="stat-chip"><div class="stat-chip-val" id="st-today">—</div><div class="stat-chip-lbl">Aujourd'hui</div></div>
    </div>

    <!-- PANEL VEILLE -->
    <div class="panel active" id="panel-veille">
      <div class="sort-row" style="flex-wrap:wrap;gap:6px;">
        <span class="sort-label">Trier par</span>
        <button class="sort-btn active" onclick="setSort('date', this)">Date</button>
        <button class="sort-btn" onclick="setSort('dispositif', this)">Dispositifs d'abord</button>
        <span class="result-count" id="result-count">— articles</span>
        <div style="flex:1"></div>
        <button onclick="collectAllMissing()" id="btn-collect-all"
          style="padding:5px 14px;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;border:1.5px solid var(--accent);background:var(--accent);color:var(--lime);white-space:nowrap;">
          📥 Tout collecter les dispositifs
        </button>
      </div>
      <div class="articles-list" id="articles-list">
        <div class="spinner"></div>
      </div>
    </div>

    <!-- PANEL DISPOSITIFS -->
    <div class="panel" id="panel-dispositifs">
      <div class="sort-row" style="gap:8px;flex-wrap:wrap;">
        <span class="result-count" id="disp-count">— dispositifs</span>
        <div style="display:flex;gap:6px;align-items:center;flex:1;flex-wrap:wrap;">
          <input id="disp-search" placeholder="Rechercher…" oninput="filterDispositifs()"
            style="padding:5px 10px;border:1px solid var(--border);border-radius:6px;font-size:11px;background:var(--surface2);color:var(--text);outline:none;min-width:140px;flex:1;">
          <select id="disp-filter-benef" onchange="filterDispositifs()"
            style="padding:5px 9px;border:1px solid var(--border);border-radius:6px;font-size:11px;background:var(--surface2);color:var(--text);outline:none;cursor:pointer;">
            <option value="">Tous bénéficiaires</option>
            <option>Collectivité</option><option>Entreprise</option><option>PME</option>
            <option>TPE</option><option>ETI</option><option>Association</option>
            <option>Start-up</option><option>ESS/Insertion</option>
            <option>Particulier</option><option>Agriculteur</option>
          </select>
          <select id="disp-filter-territoire" onchange="filterDispositifs()"
            style="padding:5px 9px;border:1px solid var(--border);border-radius:6px;font-size:11px;background:var(--surface2);color:var(--text);outline:none;cursor:pointer;">
            <option value="">Tous territoires</option>
            <option>National</option><option>Europe</option>
            <option>Nouvelle-Aquitaine</option><option>Occitanie</option>
            <option>Auvergne-Rhône-Alpes</option><option>Bretagne</option>
            <option>Normandie</option><option>Hauts-de-France</option>
            <option>Île-de-France</option><option>Grand Est</option>
            <option>Pays de la Loire</option><option>PACA</option>
            <option>Bourgogne-FC</option><option>Centre-Val de Loire</option>
          </select>

        </div>
      </div>
      <div class="disp-grid" id="disp-grid">
        <div class="spinner"></div>
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
  { key: 'comment', label: '💰 COMMENT',  tags: ['AAP','AMI','AO','ADEME','Agence de l’eau','Banque des territoires','Bpifrance','Caisse des dépôts','ANR','Aract','Dares','DDETS','DREETS','CNSA','CRESS','DILCRAH','FDVA','FEADER','FEDER','FSE','FSE+','France 2030','fonds chaleur','Financement régional','Subvention','Prêt','Avance remboursable','Crédit d’impôt','Crédit-bail','Fonds propres','Investissement','Investissement public','PTCE','LEADER','ALCOTRA','ODDS','CARSAT','FEAMPA','Fonds Barnier'] },
  { key: 'quand',   label: '📅 QUAND',    tags: ['En continu','En expérimentation','PLF 2026','Clôture 2026','Clôture 2027','Clôture 2028','Clôture août 2026','Clôture avril 2026','Clôture décembre 2025','Clôture décembre 2026','Clôture février 2026','Clôture janvier 2026','Clôture juillet 2026','Clôture juin 2026','Clôture mai 2026','Clôture mars 2026','Clôture novembre 2026','Clôture octobre 2026','Clôture septembre 2026'] },
];

// Init filter state
TAG_GROUPS.forEach(g => {
  filterState[g.key] = { logic: 'OR', active: new Set() };
});

// ── INIT ─────────────────────────────────────────────────────────────

function collectFromVeille(e) {
  e.stopPropagation(); e.preventDefault();
  var btn = e.currentTarget;
  var url = btn.getAttribute('data-url');
  var title = btn.getAttribute('data-title');
  var artId = btn.getAttribute('data-id');
  var pdfUrl = btn.getAttribute('data-pdf') || '';
  btn.disabled = true;
  btn.innerHTML = '<span class="collect-icon">⏳</span> Collecte…';
  const ctrl = new AbortController();
  const tid = setTimeout(() => ctrl.abort(), 28000);
  fetch(API + '/api/collect', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({url:url, title:title, id:artId, pdf_url:pdfUrl}),
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
      btn.innerHTML = '⚠ ' + (d.error.length < 40 ? d.error : 'Erreur'); btn.disabled=false;
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
          btn.innerHTML = '✅ Collecté !';
          btn.style.cssText='background:var(--lime);color:var(--accent)';
          loadDispositifs();
          showToast('Dispositif ajouté à la base !');
        }
      });
    }
  }).catch(function(){ btn.innerHTML='⚠ Erreur réseau'; btn.disabled=false; });
}
async function init() {
  buildSidebar();
  updateLockState();
  await Promise.all([loadArticles(), loadDispositifs()]);
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

async function loadDispositifs() {
  try {
    const res = await fetch(API + '/api/dispositifs');
    allDispositifs = await res.json();
    document.getElementById('st-dispositifs').textContent = allDispositifs.length;
    renderDispositifs(allDispositifs);
  } catch(e) {}
}

function updateStats() {
  document.getElementById('st-articles').textContent = allArticles.length;
  const today = new Date().toDateString();
  const todayCount = allArticles.filter(a => new Date(a.scraped_at).toDateString() === today).length;
  document.getElementById('st-today').textContent = todayCount;
  const cdcCount = allArticles.filter(a => a.pdf_url).length;
  document.getElementById('st-cdc').textContent = cdcCount;
  renderCDC(allArticles.filter(a => a.pdf_url));
}

// ── FILTERING ─────────────────────────────────────────────────────────
function applyFilters() {
  let filtered = allArticles;

  // Search
  if (searchQ) {
    const q = searchQ.toLowerCase();
    filtered = filtered.filter(a =>
      (a.title||'').toLowerCase().includes(q) ||
      (a.summary||'').toLowerCase().includes(q) ||
      (a.source||'').toLowerCase().includes(q)
    );
  }

  // Tag filters
  TAG_GROUPS.forEach(g => {
    const active = filterState[g.key].active;
    if (!active.size) return;
    filtered = filtered.filter(a => {
      const tags = Array.isArray(a.tags)?a.tags:JSON.parse(a.tags||'[]');
      return [...active].some(t => tags.includes(t));
    });
  });

  // Sort
  if (sortMode === 'date') {
    filtered.sort((a,b) => new Date(b.scraped_at) - new Date(a.scraped_at));
  } else {
    filtered.sort((a,b) => {
      const ad = (Array.isArray(a.tags)?a.tags:JSON.parse(a.tags||'[]')).includes('⭐ Dispositif');
      const bd = (Array.isArray(b.tags)?b.tags:JSON.parse(b.tags||'[]')).includes('⭐ Dispositif');
      if (ad && !bd) return -1; if (!ad && bd) return 1;
      return new Date(b.scraped_at) - new Date(a.scraped_at);
    });
  }

  document.getElementById('result-count').textContent = filtered.length + ' article' + (filtered.length > 1 ? 's' : '');
  renderArticles(filtered);
}

// ── RENDER ARTICLES ───────────────────────────────────────────────────
function renderArticles(list) {
  const DISP = '⭐ Dispositif', ACT = '⭐ Actualité';
  const disps = list.filter(a => { const t=Array.isArray(a.tags)?a.tags:JSON.parse(a.tags||'[]'); return t.indexOf(DISP)>=0; });
  const acts  = list.filter(a => { const t=Array.isArray(a.tags)?a.tags:JSON.parse(a.tags||'[]'); return t.indexOf(ACT)>=0; });
  const container = document.getElementById('articles-list');
  if (!disps.length && !acts.length) {
    container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠️</div><div class="empty-state-title">Aucun résultat</div><p>Sélectionnez ⭐ Dispositif ou ⭐ Actualité</p></div>';
    return;
  }
  let html = '';
  if (disps.length) {
    html += '<div class="section-label">⭐ Dispositifs <span class="section-count">'+disps.length+'</span></div>';
    html += renderArticleCards(disps, true);
  }
  if (acts.length) {
    html += '<div class="section-label">📰 Actualités <span class="section-count">'+acts.length+'</span></div>';
    html += renderArticleCards(acts, false);
  }
  container.innerHTML = html;
}

function renderArticleCards(list, showCollect) {
  return list.map((a, i) => {
    const tags = Array.isArray(a.tags)?a.tags:JSON.parse(a.tags||'[]');
    const isDisp = tags.indexOf('⭐ Dispositif')>=0;
    const date = a.scraped_at ? new Date(a.scraped_at).toLocaleDateString('fr-FR',{day:'numeric',month:'short'}) : '';
    const subTags = tags.filter(t => !t.startsWith('⭐'));
    const typeBadge = isDisp ? '<span class="article-tag ref">⭐ Dispositif</span>' : '<span class="article-tag">⭐ Actualité</span>';
    const tagsHtml = subTags.map(t=>'<span class="article-tag">'+t+'</span>').join('');
    const cdcInfo = a.pdf_url ? `<a class="cdc-inline-link" href="${a.pdf_url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">📋 CDC</a>` : '';
    const safeUrl = (a.url||'').replace(/"/g,'&quot;');
    const safeTitle = (a.title||'').replace(/"/g,'&quot;');
    const safePdf = (a.pdf_url||'').replace(/"/g,'&quot;');
    const collectBtn = showCollect
      ? `<button class="btn-collect" data-url="${safeUrl}" data-title="${safeTitle}" data-id="${a.id||0}" data-pdf="${safePdf}" onclick="collectFromVeille(event)"><span class="collect-icon">💾</span> Collecter</button>`
      : '';
    return `<a class="article-card${isDisp?' is-dispositif':''}" href="${a.url}" target="_blank" rel="noopener" style="animation-delay:${Math.min(i*0.03,0.4)}s">
      <div class="article-card-top">
        <div><div class="article-card-source">${a.source||''}</div><div class="article-card-date">${date}</div></div>
        <div class="article-card-title">${a.title}</div>
      </div>
      ${a.summary?`<div class="article-card-summary">${a.summary}</div>`:''}
      <div class="article-card-tags">${typeBadge}${tagsHtml}${cdcInfo}</div>
      ${collectBtn ? `<div class="card-collect-row" onclick="event.preventDefault()">${collectBtn}</div>` : ''}
    </a>`;
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
function filterDispositifs() {
  const q      = (document.getElementById('disp-search')?.value || '').toLowerCase();
  const benef  = (document.getElementById('disp-filter-benef')?.value || '').toLowerCase();
  const terr   = (document.getElementById('disp-filter-territoire')?.value || '').toLowerCase();
  let list = allDispositifs;
  if (q)     list = list.filter(d => (d.titre||'').toLowerCase().includes(q) || (d.guichet_financeur||'').toLowerCase().includes(q));
  if (benef) list = list.filter(d => (d.beneficiaire||'').toLowerCase().includes(benef));
  if (terr)  list = list.filter(d => (d.territoire||'').toLowerCase().includes(terr));
  renderDispositifs(list);
}

// ── COLLECT ALL MISSING ───────────────────────────────────────────────
async function collectAllMissing() {
  // Récupérer les articles de type Dispositif non encore collectés
  const btn = document.getElementById('btn-collect-all');
  btn.disabled = true;
  btn.textContent = '⏳ Chargement…';
  try {
    // Charger tous les articles dispositifs
    const arts = await fetch(API + '/api/articles?limit=2000').then(r => r.json());
    const collected = new Set(allDispositifs.map(d => d.source_url).filter(Boolean));
    const toCollect = arts.filter(a => {
      const tags = Array.isArray(a.tags) ? a.tags : JSON.parse(a.tags || '[]');
      return tags.includes('⭐ Dispositif') && !collected.has(a.url);
    });
    if (!toCollect.length) {
      showToast('✅ Tous les dispositifs sont déjà collectés !');
      btn.disabled = false;
      btn.innerHTML = '📥 Tout collecter';
      return;
    }
    if (!confirm('Collecter ' + toCollect.length + ' dispositif(s) non encore collectés ? Cela utilisera des crédits API Claude.')) {
      btn.disabled = false;
      btn.innerHTML = '📥 Tout collecter';
      return;
    }
    btn.textContent = '⏳ 0/' + toCollect.length;
    let done = 0, errors = 0;
    for (const a of toCollect) {
      try {
        const d = await fetch(API + '/api/collect', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({url: a.url, title: a.title, id: a.id, pdf_url: a.pdf_url || ''})
        }).then(r => r.json());
        if (!d.error) {
          await fetch(API + '/api/dispositifs', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify(d)
          });
          done++;
        } else { errors++; }
      } catch(e) { errors++; }
      btn.textContent = '⏳ ' + (done + errors) + '/' + toCollect.length;
    }
    showToast('✅ ' + done + ' collecté(s)' + (errors ? ' — ' + errors + ' erreur(s)' : ''));
    loadDispositifs();
  } catch(e) {
    showToast('❌ Erreur : ' + e.message);
  }
  btn.disabled = false;
  btn.innerHTML = '📥 Tout collecter';
}

// ── RENDER CDC ────────────────────────────────────────────────────────
function renderCDC(list) {
  const container = document.getElementById('cdc-list');
  document.getElementById('cdc-count').textContent = list.length + ' document' + (list.length > 1 ? 's' : '');
  if (!list.length) {
    container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📋</div><div class="empty-state-title">Aucun cahier des charges trouvé</div><p>Lancez une analyse CDC depuis l’espace de veille</p></div>';
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
function exportDispPptx() {
  if (currentDispId) window.open(API + '/api/dispositifs/' + currentDispId + '/export-pptx', '_blank');
}

// ── NAV ───────────────────────────────────────────────────────────────
function switchTab(tab, btn) {
  activeTab = tab;
  document.querySelectorAll('.header-tab').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById('panel-' + tab).classList.add('active');
  if (tab === 'veille360') loadV360Sessions();
}

// ── PRÉ-VEILLE 360° ───────────────────────────────────────────────────
const PROMPT_360_C = `You are "Recherche 360°", a Senior Consultant in public and private financial engineering specialized exclusively in identifying CAPEX funding for investment projects carried by local authorities or private entities eligible for public investment aid. Your sole mission is to conduct exhaustive strategic pre-screening to verify that all schemes financing tangible assets have been identified. Scope: strictly CAPEX only (real estate, works, construction, rehabilitation, equipment, networks, energy performance, etc.). Apply a strict three-criteria eligibility test: 1) Beneficiary legally compatible. 2) Eligible base explicitly finances tangible CAPEX. 3) Purpose coherent with project nature. Return a structured HTML table with columns: Thématique | Territoire | Financeur | Instructeur | Nom exact du dispositif | Type (subvention/prêt/prime) | Base CAPEX éligible | Pertinence stratégique | Montant/Taux indicatif | Statut | Lien officiel. Color-code rows. Never invent schemes. Conclude with exhaustiveness validation. Language: French. Return only clean HTML, no markdown.`;

async function runV360() {
  const clientName = document.getElementById('v360-client-input').value.trim();
  const project    = document.getElementById('v360-project').value.trim();
  const status     = document.getElementById('v360-status-inline');
  if (!clientName) { document.getElementById('v360-client-input').focus(); showToast('Indiquez un nom de client / dossier'); return; }
  if (!project)    { document.getElementById('v360-project').focus(); showToast('Décrivez le projet'); return; }
  const btn = document.getElementById('v360-run-btn');
  btn.disabled = true; btn.textContent = '⏳ Analyse…';
  status.textContent = 'Interrogation de l’IA…';
  try {
    const resp = await fetch(API + '/api/veille360', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 4000,
        system: PROMPT_360_C,
        messages: [{role:'user', content: project}]
      })
    });
    const data = await resp.json();
    const html_result = data.content && data.content.find(b => b.type === 'text')
      ? data.content.find(b => b.type === 'text').text : (data.error || 'Aucun résultat.');
    // Sauvegarder en DB
    await fetch(API + '/api/veille360/sessions', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({client_name: clientName, project_desc: project, result_html: html_result})
    });
    status.textContent = '✅ Analyse sauvegardée dans le dossier "' + clientName + '"';
    document.getElementById('v360-client-input').value = '';
    document.getElementById('v360-project').value = '';
    loadV360Sessions();
    openV360Modal(clientName, html_result);
  } catch(e) {
    status.textContent = '❌ Erreur : ' + e.message;
  }
  btn.disabled = false; btn.textContent = '🔍 Lancer une analyse';
}

async function loadV360Sessions() {
  const list = document.getElementById('v360-sessions-list');
  const count = document.getElementById('v360-sessions-count');
  try {
    const sessions = await fetch(API + '/api/veille360/sessions').then(r => r.json());
    count.textContent = sessions.length + ' analyse' + (sessions.length > 1 ? 's' : '');
    if (!sessions.length) {
      list.innerHTML = '<div style="font-size:12px;color:var(--muted);padding:12px 0;">Aucune analyse — lancez votre première pré-veille 360° ci-dessus.</div>';
      return;
    }
    list.innerHTML = sessions.map(s => {
      const d = new Date(s.created_at).toLocaleDateString('fr-FR', {day:'numeric', month:'short', year:'numeric'});
      const desc = (s.project_desc || '').slice(0, 80) + ((s.project_desc||'').length > 80 ? '…' : '');
      return `<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px 14px;display:flex;align-items:center;gap:10px;cursor:pointer;" onclick="openV360Session(${s.id})">
        <div style="flex:1;min-width:0;">
          <div style="font-weight:700;font-size:12px;color:var(--accent);">${s.client_name}</div>
          <div style="font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${desc || '—'}</div>
        </div>
        <div style="font-size:10px;color:var(--muted2);white-space:nowrap;">${d}</div>
        <button onclick="event.stopPropagation();deleteV360Session(${s.id})" title="Supprimer"
          style="background:none;border:1px solid rgba(200,57,43,.2);color:#c8392b;border-radius:5px;width:24px;height:24px;cursor:pointer;font-size:11px;flex-shrink:0;">✕</button>
      </div>`;
    }).join('');
  } catch(e) {
    list.innerHTML = '<div style="font-size:12px;color:var(--muted);">Erreur chargement</div>';
  }
}

async function openV360Session(id) {
  try {
    const s = await fetch(API + '/api/veille360/sessions/' + id).then(r => r.json());
    openV360Modal(s.client_name, s.result_html);
  } catch(e) { showToast('Erreur chargement'); }
}

function openV360Modal(clientName, htmlContent) {
  document.getElementById('v360-modal-title').textContent = '🔍 Analyse 360° — ' + clientName;
  document.getElementById('v360-modal-body').innerHTML = htmlContent;
  document.getElementById('v360-modal').style.display = 'flex';
}

async function deleteV360Session(id) {
  if (!confirm('Supprimer cette analyse ?')) return;
  await fetch(API + '/api/veille360/sessions/' + id, {method: 'DELETE'});
  loadV360Sessions();
}

function setSort(mode, btn) {
  sortMode = mode;
  document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  applyFilters();
}

let searchTimer;
function onSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    searchQ = document.getElementById('search').value.trim();
    applyFilters();
  }, 250);
}

// ── TOAST ─────────────────────────────────────────────────────────────
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2800);
}

// ── START ─────────────────────────────────────────────────────────────
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
</html>"""

LANDING_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SubstanCiel — Plateforme de veille intelligente</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #f4f3ef; --surface: #ffffff; --surface2: #f0efe9;
  --border: #e2e0d8; --text: #1a1a18; --text2: #5a5a52; --muted: #9a9a90;
  --accent: #1a3c2e; --lime: #c8e84e; --lime-soft: #e8f5b0;
}
html { scroll-behavior: smooth; }
body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); }
a { text-decoration: none; }

/* ── NAV ── */
.nav {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 52px; height: 62px;
  background: rgba(244,243,239,.94); backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 100;
}
.nav-logo {
  font-family: 'Syne', sans-serif; font-weight: 800; font-size: 19px;
  color: var(--accent); display: flex; align-items: center; gap: 9px;
}
.logo-dot {
  width: 8px; height: 8px; border-radius: 50%; background: var(--lime);
  box-shadow: 0 0 0 4px rgba(200,232,78,.25);
  animation: sc-pulse 2.4s ease-in-out infinite;
}
@keyframes sc-pulse {
  0%,100% { box-shadow: 0 0 0 4px rgba(200,232,78,.2); }
  50%      { box-shadow: 0 0 0 8px rgba(200,232,78,.07); }
}
.nav-links { display: flex; align-items: center; gap: 28px; }
.nav-links a { font-size: 13px; font-weight: 500; color: var(--text2); transition: color .15s; }
.nav-links a:hover { color: var(--accent); }
.nav-cta {
  background: var(--accent) !important; color: var(--lime) !important;
  padding: 7px 18px; border-radius: 100px; font-weight: 600 !important; font-size: 13px !important;
  transition: transform .15s, box-shadow .15s;
}
.nav-cta:hover { transform: translateY(-1px); box-shadow: 0 6px 18px rgba(26,60,46,.28); }

/* ── HERO ── */
.hero {
  padding: 88px 52px 72px;
  display: flex; flex-direction: column; align-items: center; text-align: center;
  background: var(--bg); position: relative; overflow: hidden;
}
.hero-grid {
  position: absolute; inset: 0; pointer-events: none;
  background-image: linear-gradient(var(--border) 1px, transparent 1px),
                    linear-gradient(90deg, var(--border) 1px, transparent 1px);
  background-size: 72px 72px; opacity: .45;
  mask-image: radial-gradient(ellipse 80% 80% at 50% 40%, black, transparent);
  -webkit-mask-image: radial-gradient(ellipse 80% 80% at 50% 40%, black, transparent);
}
.hero-blob {
  position: absolute; border-radius: 50%;
  background: var(--lime); opacity: .08; pointer-events: none;
}
.eyebrow {
  position: relative;
  font-size: 11px; font-weight: 600; letter-spacing: .13em; text-transform: uppercase;
  color: var(--accent); background: var(--lime-soft);
  border: 1px solid rgba(200,232,78,.5); padding: 5px 16px; border-radius: 100px;
  margin-bottom: 26px; display: inline-block;
}
.hero-title {
  position: relative;
  font-family: 'Syne', sans-serif; font-weight: 800;
  font-size: clamp(38px, 5.5vw, 68px); line-height: 1.06; letter-spacing: -.03em;
  color: var(--accent); max-width: 840px; margin-bottom: 22px;
}
.hl { display: inline-block; position: relative; }
.hl::after {
  content: ''; position: absolute; left: 0; right: 0; bottom: 4px;
  height: 7px; background: var(--lime); z-index: -1; border-radius: 3px; opacity: .65;
}
.hero-sub {
  position: relative; font-size: 17px; color: var(--text2);
  line-height: 1.65; max-width: 520px; margin-bottom: 40px; font-weight: 300;
}
.hero-btns {
  position: relative;
  display: flex; gap: 12px; flex-wrap: wrap; justify-content: center; margin-bottom: 56px;
}
.btn-p {
  background: var(--accent); color: var(--lime); padding: 13px 28px; border-radius: 100px;
  font-weight: 600; font-size: 14px; border: none; font-family: 'DM Sans', sans-serif;
  display: inline-flex; align-items: center; gap: 7px;
  transition: transform .15s, box-shadow .15s; cursor: pointer;
}
.btn-p:hover { transform: translateY(-2px); box-shadow: 0 10px 28px rgba(26,60,46,.28); }
.btn-s {
  background: var(--surface); color: var(--accent); padding: 13px 24px; border-radius: 100px;
  font-weight: 500; font-size: 14px; border: 1.5px solid var(--border);
  font-family: 'DM Sans', sans-serif;
  display: inline-flex; align-items: center; gap: 7px; transition: border-color .15s, background .15s;
}
.btn-s:hover { border-color: var(--accent); background: var(--lime-soft); }

/* STATS */
.stats {
  position: relative;
  display: grid; grid-template-columns: repeat(3, 1fr);
  background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
  max-width: 760px; width: 100%; overflow: hidden;
}
.stat { padding: 22px 28px; text-align: center; border-right: 1px solid var(--border); }
.stat:last-child { border-right: none; }
.stat-n { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 32px; color: var(--accent); line-height: 1; }
.stat-n em { color: var(--lime); font-style: normal; }
.stat-l { font-size: 11px; color: var(--muted); margin-top: 5px; }

/* ── SECTION ESPACES ── */
.section { padding: 80px 52px; background: var(--bg); }
.sec-head { text-align: center; margin-bottom: 52px; }
.sec-eye {
  font-size: 10px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase;
  color: var(--muted); margin-bottom: 10px;
}
.sec-title {
  font-family: 'Syne', sans-serif; font-weight: 800;
  font-size: clamp(24px, 3vw, 40px); color: var(--accent);
  letter-spacing: -.02em; margin-bottom: 12px; line-height: 1.1;
}
.sec-sub { font-size: 15px; color: var(--text2); max-width: 480px; margin: 0 auto; line-height: 1.65; }

/* GRILLE 3 CARTES */
.cards-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 20px; max-width: 1100px; margin: 0 auto;
}

/* CARTE ESPACE */
.ecard {
  border-radius: 22px; display: flex; flex-direction: column;
  transition: transform .22s, box-shadow .22s; overflow: hidden;
}
.ecard:hover { transform: translateY(-5px); box-shadow: 0 22px 50px rgba(26,60,46,.13); }
.ecard-dark  { background: var(--accent); }
.ecard-white { background: var(--surface); border: 1.5px solid var(--border); }
.ecard-gray  { background: var(--surface2); border: 1.5px dashed var(--border); opacity: .76; }

.ecard-inner { padding: 32px 28px 28px; flex: 1; display: flex; flex-direction: column; }

.etag {
  font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
  margin-bottom: 22px; display: flex; align-items: center; gap: 8px;
}
.ecard-dark  .etag { color: rgba(200,232,78,.4); }
.ecard-white .etag { color: var(--muted); }
.ecard-gray  .etag { color: var(--muted); }

.ebadge { font-size: 9px; padding: 2px 8px; border-radius: 100px; font-weight: 700; }
.ebadge-live  { background: rgba(200,232,78,.2);  color: var(--lime); }
.ebadge-liveg { background: rgba(200,232,78,.18); color: #3a6020; }
.ebadge-wip   { background: var(--border);        color: var(--muted); }

.eicon {
  width: 48px; height: 48px; border-radius: 13px;
  display: flex; align-items: center; justify-content: center; margin-bottom: 18px;
}
.ecard-dark  .eicon { background: rgba(200,232,78,.12); }
.ecard-white .eicon { background: var(--lime-soft); }
.ecard-gray  .eicon { background: var(--border); }

.ename {
  font-family: 'Syne', sans-serif; font-weight: 800;
  font-size: 22px; line-height: 1.1; margin-bottom: 9px;
}
.ecard-dark  .ename { color: var(--lime); }
.ecard-white .ename { color: var(--accent); }
.ecard-gray  .ename { color: var(--text2); }

.edesc { font-size: 13.5px; line-height: 1.6; margin-bottom: 22px; }
.ecard-dark  .edesc { color: rgba(244,243,239,.58); }
.ecard-white .edesc { color: var(--text2); }
.ecard-gray  .edesc { color: var(--muted); }

.efeats { list-style: none; flex: 1; display: flex; flex-direction: column; gap: 8px; margin-bottom: 28px; }
.efeats li { font-size: 13px; display: flex; align-items: flex-start; gap: 9px; line-height: 1.45; }
.ecard-dark  .efeats li { color: rgba(244,243,239,.73); }
.ecard-white .efeats li { color: var(--text2); }
.ecard-gray  .efeats li { color: var(--muted); }
.fdot { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; margin-top: 5px; }
.ecard-dark  .fdot { background: var(--lime); }
.ecard-white .fdot { background: var(--accent); }
.ecard-gray  .fdot { background: var(--border); }

.eurl {
  font-size: 10px; font-weight: 500; letter-spacing: .04em;
  margin-bottom: 10px; display: block;
}
.ecard-dark  .eurl { color: rgba(200,232,78,.28); }
.ecard-white .eurl { color: var(--muted); }
.ecard-gray  .eurl { color: var(--border); }

.ebtn {
  display: inline-flex; align-items: center; gap: 7px;
  font-weight: 600; font-size: 13px; padding: 11px 22px; border-radius: 100px;
  cursor: pointer; border: none; font-family: 'DM Sans', sans-serif; transition: all .15s;
}
.ecard-dark  .ebtn { background: var(--lime); color: var(--accent); }
.ecard-dark  .ebtn:hover { background: #d8f060; transform: translateX(2px); }
.ecard-white .ebtn { background: var(--accent); color: var(--lime); }
.ecard-white .ebtn:hover { box-shadow: 0 6px 18px rgba(26,60,46,.22); transform: translateX(2px); }
.ecard-gray  .ebtn { background: var(--border); color: var(--muted); cursor: not-allowed; }

/* ── PIPELINE ── */
.pipe-wrap { padding: 0 52px 80px; }
.pipeline {
  background: var(--accent); border-radius: 26px;
  padding: 60px 52px; position: relative; overflow: hidden;
}
.pipe-blob { position: absolute; border-radius: 50%; background: var(--lime); opacity: .05; pointer-events: none; }
.pipe-eye { font-size: 10px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: rgba(200,232,78,.4); margin-bottom: 8px; }
.pipe-title { font-family: 'Syne', sans-serif; font-weight: 800; font-size: clamp(22px, 2.8vw, 34px); color: var(--lime); letter-spacing: -.02em; line-height: 1.1; margin-bottom: 10px; }
.pipe-sub { font-size: 14px; color: rgba(244,243,239,.48); max-width: 460px; line-height: 1.6; margin-bottom: 44px; }
.pipe-steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 3px; position: relative; }
.pipe-step {
  background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.09);
  border-radius: 14px; padding: 22px 18px; position: relative; transition: background .18s;
}
.pipe-step:hover { background: rgba(255,255,255,.09); }
.pipe-num { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 28px; color: rgba(200,232,78,.14); line-height: 1; margin-bottom: 12px; }
.pipe-t { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 13px; color: var(--lime); margin-bottom: 7px; }
.pipe-d { font-size: 12px; color: rgba(244,243,239,.5); line-height: 1.55; }
.pipe-arr {
  position: absolute; right: -14px; top: 50%; transform: translateY(-50%);
  width: 26px; height: 26px; background: var(--accent);
  border: 1px solid rgba(200,232,78,.18); border-radius: 50%;
  display: flex; align-items: center; justify-content: center; z-index: 2;
}
.pipe-step:last-child .pipe-arr { display: none; }

/* ── AGENT ── */
.agent { padding: 80px 52px; }
.agent-inner { display: grid; grid-template-columns: 1fr 1fr; gap: 72px; align-items: center; max-width: 1100px; margin: 0 auto; }
.agent-pts { display: flex; flex-direction: column; gap: 20px; margin-top: 24px; }
.apt { display: flex; gap: 13px; align-items: flex-start; }
.apt-ico { width: 32px; height: 32px; border-radius: 10px; background: var(--lime-soft); flex-shrink: 0; display: flex; align-items: center; justify-content: center; margin-top: 2px; }
.apt-t { font-weight: 600; font-size: 14px; color: var(--accent); margin-bottom: 3px; }
.apt-d { font-size: 13px; color: var(--text2); line-height: 1.5; }

.terminal { background: var(--surface); border: 1px solid var(--border); border-radius: 18px; padding: 22px; }
.tbar { display: flex; align-items: center; gap: 6px; margin-bottom: 18px; }
.tdot { width: 10px; height: 10px; border-radius: 50%; }
.tlbl { font-size: 11px; color: var(--muted); margin-left: 8px; font-weight: 500; }
.tlog { display: flex; flex-direction: column; gap: 7px; min-height: 130px; }
.tline { display: flex; gap: 9px; align-items: flex-start; }
.ttag { font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 4px; flex-shrink: 0; margin-top: 2px; letter-spacing: .04em; }
.tok  { background: #e8f5e8; color: #2a7a2a; }
.tdisp{ background: var(--lime-soft); color: var(--accent); }
.tact { background: #e8eeff; color: #2a4bb0; }
.tdel { background: #fde8e8; color: #b02a2a; }
.ttxt { font-size: 12px; color: var(--text2); line-height: 1.4; }
.tprog { background: var(--surface2); border-radius: 5px; height: 5px; margin-top: 16px; overflow: hidden; }
.tpbar { height: 100%; background: var(--lime); border-radius: 5px; transition: width 1s ease; width: 0%; }
.tmeta { display: flex; justify-content: space-between; font-size: 11px; color: var(--muted); margin-top: 5px; }

/* ── FOOTER ── */
footer {
  background: var(--accent); padding: 48px 52px;
  display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 20px;
}
.flogo { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 20px; color: var(--lime); }
.ftag  { font-size: 12px; color: rgba(200,232,78,.38); margin-top: 4px; }
.flinks { display: flex; gap: 26px; }
.flinks a { font-size: 13px; color: rgba(244,243,239,.42); transition: color .15s; }
.flinks a:hover { color: var(--lime); }
</style>
</head>
<body>

<!-- ── NAV ── -->
<nav class="nav">
  <div class="nav-logo">
    <div class="logo-dot"></div>
    SubstanCiel
  </div>
  <div class="nav-links">
    <a href="#espaces">Les espaces</a>
    <a href="#pipeline">Pipeline</a>
    <a href="#agent">Agent IA</a>
    <a href="/app" class="nav-cta">Espace Curation &rarr;</a>
  </div>
</nav>

<!-- ── HERO ── -->
<div class="hero">
  <div class="hero-grid"></div>
  <div class="hero-blob" style="width:580px;height:580px;top:-150px;right:-90px;"></div>
  <div class="hero-blob" style="width:260px;height:260px;bottom:30px;left:-50px;"></div>

  <div class="eyebrow">Plateforme de veille intelligente</div>
  <h1 class="hero-title">
    La veille strat&eacute;gique<br>
    <span class="hl">automatis&eacute;e</span> pour les<br>
    experts du financement
  </h1>
  <p class="hero-sub">
    Scraping intelligent sur 91 sources, qualification IA et collecte structur&eacute;e en 19 champs.
    Ne manquez plus aucun dispositif de financement public.
  </p>
  <div class="hero-btns">
    <a href="/app" class="btn-p">
      Espace Curation
      <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M1.5 6.5h10M8 3l4 3.5-4 3.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </a>
    <a href="/consultant" class="btn-s">
      Espace Collecte
      <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M1.5 6.5h10M8 3l4 3.5-4 3.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </a>
  </div>
  <div class="stats">
    <div class="stat">
      <div class="stat-n">91<em>+</em></div>
      <div class="stat-l">Sources surveill&eacute;es</div>
    </div>
    <div class="stat">
      <div class="stat-n">6<em>h</em></div>
      <div class="stat-l">Cycle de scraping auto</div>
    </div>
    <div class="stat">
      <div class="stat-n">19</div>
      <div class="stat-l">Champs par dispositif</div>
    </div>
  </div>
</div>

<!-- ── ESPACES ── -->
<div id="espaces" class="section">
  <div class="sec-head">
    <div class="sec-eye">Les 3 espaces</div>
    <h2 class="sec-title">Un outil, trois niveaux d'usage</h2>
    <p class="sec-sub">De la captation brute &agrave; la gestion de projet client, chaque espace r&eacute;pond &agrave; un besoin m&eacute;tier distinct.</p>
  </div>

  <div class="cards-grid">

    <!-- 01 CURATION -->
    <div class="ecard ecard-dark">
      <div class="ecard-inner">
        <div class="etag">
          <span>01</span>
          <span class="ebadge ebadge-live">&#9679; Actif</span>
        </div>
        <div class="eicon">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path d="M11 2l2.5 6H20l-5.5 4 2 6L11 14l-5.5 4 2-6L2 8h6.5L11 2z" stroke="rgba(200,232,78,.75)" stroke-width="1.6" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="ename">Espace Curation</div>
        <p class="edesc">Le back-office du veilleur. Supervision du flux complet, qualification et alimentation de la base consultants.</p>
        <ul class="efeats">
          <li><span class="fdot"></span>Scraping automatique toutes les 6h sur 91 sources</li>
          <li><span class="fdot"></span>Agent IA&nbsp;: tagging automatique + suppression du bruit</li>
          <li><span class="fdot"></span>D&eacute;tection CDC au scraping (PDF, Word&hellip;)</li>
          <li><span class="fdot"></span>Dashboard stats, Veille 360&deg;, export PowerPoint</li>
          <li><span class="fdot"></span>Gestion des sources par dossier / r&eacute;pertoire</li>
        </ul>
        <span class="eurl">veille-q32f.onrender.com/app</span>
        <a href="/app" class="ebtn">
          Ouvrir la curation
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none"><path d="M1 5.5h9M6.5 2l3 3.5-3 3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </a>
      </div>
    </div>

    <!-- 02 COLLECTE -->
    <div class="ecard ecard-white">
      <div class="ecard-inner">
        <div class="etag">
          <span>02</span>
          <span class="ebadge ebadge-liveg">&#9679; Actif</span>
        </div>
        <div class="eicon">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path d="M14 2H8a2 2 0 00-2 2v14a2 2 0 002 2h8a2 2 0 002-2V8l-4-6z" stroke="#1a3c2e" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M14 2v6h6M8 13h6M8 17h4" stroke="#1a3c2e" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="ename">Espace Collecte</div>
        <p class="edesc">L'interface consultants en lecture seule. Acc&egrave;s &agrave; toute la veille qualifi&eacute;e, collecte directe des dispositifs en base partagée.</p>
        <ul class="efeats">
          <li><span class="fdot"></span>Vue s&eacute;par&eacute;e&nbsp;: &#11088; Dispositifs / &#128240; Actualit&eacute;s</li>
          <li><span class="fdot"></span>Filtres&nbsp;: type, b&eacute;n&eacute;ficiaire, territoire, m&eacute;canisme</li>
          <li><span class="fdot"></span>Bouton &laquo;&nbsp;Collecter&nbsp;&raquo; &rarr; Claude analyse le CDC en priorit&eacute;</li>
          <li><span class="fdot"></span>Base dispositifs partag&eacute;e, doublon impossible</li>
          <li><span class="fdot"></span>Acc&egrave;s multi-consultant simultan&eacute;, lecture seule</li>
        </ul>
        <span class="eurl">veille-q32f.onrender.com/consultant</span>
        <a href="/consultant" class="ebtn">
          Ouvrir la collecte
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none"><path d="M1 5.5h9M6.5 2l3 3.5-3 3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </a>
      </div>
    </div>

    <!-- 03 PROJET -->
    <div class="ecard ecard-gray">
      <div class="ecard-inner">
        <div class="etag">
          <span>03</span>
          <span class="ebadge ebadge-wip">En d&eacute;veloppement</span>
        </div>
        <div class="eicon">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <rect x="3" y="3" width="16" height="12" rx="2" stroke="#9a9a90" stroke-width="1.6"/>
            <path d="M7 19h8M11 15v4M7 8h2M11 8h4M7 11h8" stroke="#9a9a90" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="ename">Espace Projet</div>
        <p class="edesc" style="color:#9a9a90;font-style:italic;">En programmation</p>
        <ul class="efeats" style="display:none">
          <li><span class="fdot"></span>placeholder</li>
          <li><span class="fdot"></span>placeholder</li>
          <li><span class="fdot"></span>placeholder</li>
          <li><span class="fdot"></span>placeholder automatique</li>
          <li><span class="fdot"></span>placeholder</li>
        </ul>
        <span class="eurl">Disponible prochainement</span>
        <button class="ebtn" disabled>Bient&ocirc;t disponible</button>
      </div>
    </div>

  </div>
</div>

<!-- ── PIPELINE ── -->
<div id="pipeline" class="pipe-wrap">
  <div class="pipeline">
    <div class="pipe-blob" style="width:420px;height:420px;top:-160px;right:-60px;"></div>
    <div class="pipe-eye">Pipeline automatis&eacute;</div>
    <div class="pipe-title">De la source brute &agrave; la fiche structur&eacute;e</div>
    <div class="pipe-sub">Chaque article suit un pipeline en 4 &eacute;tapes avant d'&ecirc;tre disponible pour les consultants.</div>
    <div class="pipe-steps">
      <div class="pipe-step">
        <div class="pipe-num">01</div>
        <div class="pipe-t">Scraping</div>
        <div class="pipe-d">91 sources surveill&eacute;es. Nouveaux articles et CDC d&eacute;tect&eacute;s &agrave; chaque cycle de 6h.</div>
        <div class="pipe-arr">
          <svg width="9" height="9" viewBox="0 0 9 9" fill="none"><path d="M1 4.5h7M5 2l3 2.5L5 7" stroke="rgba(200,232,78,.55)" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </div>
      </div>
      <div class="pipe-step">
        <div class="pipe-num">02</div>
        <div class="pipe-t">Curation IA</div>
        <div class="pipe-d">Agent Claude Haiku&nbsp;: tag Dispositif / Actualit&eacute;, sous-tags QUI/O&Ugrave;/COMMENT, suppression du bruit.</div>
        <div class="pipe-arr">
          <svg width="9" height="9" viewBox="0 0 9 9" fill="none"><path d="M1 4.5h7M5 2l3 2.5L5 7" stroke="rgba(200,232,78,.55)" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </div>
      </div>
      <div class="pipe-step">
        <div class="pipe-num">03</div>
        <div class="pipe-t">Collecte</div>
        <div class="pipe-d">1&nbsp;clic consultant. Claude analyse le CDC PDF en priorit&eacute; &rarr; fiche structur&eacute;e en 19 champs.</div>
        <div class="pipe-arr">
          <svg width="9" height="9" viewBox="0 0 9 9" fill="none"><path d="M1 4.5h7M5 2l3 2.5L5 7" stroke="rgba(200,232,78,.55)" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </div>
      </div>
      <div class="pipe-step">
        <div class="pipe-num">04</div>
        <div class="pipe-t">Base partag&eacute;e</div>
        <div class="pipe-d">Fiche disponible pour toute l'&eacute;quipe. Export PPTX en 1&nbsp;clic, doublon impossible.</div>
      </div>
    </div>
  </div>
</div>

<!-- ── AGENT IA ── -->
<div id="agent" class="agent">
  <div class="agent-inner">
    <div>
      <div class="sec-eye">Agent IA</div>
      <h2 class="sec-title">Curation automatique,<br>z&eacute;ro bruit</h2>
      <p class="sec-sub">Lancez l'agent depuis l'espace curation. Il analyse chaque article, attribue les bons tags et &eacute;limine ce qui ne m&eacute;rite pas attention.</p>
      <div class="agent-pts">
        <div class="apt">
          <div class="apt-ico">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 8h4l2-4 3 8 2-4h3" stroke="#1a3c2e" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </div>
          <div>
            <div class="apt-t">Tagging contextuel</div>
            <div class="apt-d">Type, b&eacute;n&eacute;ficiaires, territoire, m&eacute;canisme &mdash; jusqu'&agrave; 8 tags par article.</div>
          </div>
        </div>
        <div class="apt">
          <div class="apt-ico">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M13 4L6 12l-3-3" stroke="#1a3c2e" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </div>
          <div>
            <div class="apt-t">Suppression du bruit</div>
            <div class="apt-d">Articles hors-sujet supprim&eacute;s automatiquement, avec confirmation avant ex&eacute;cution.</div>
          </div>
        </div>
        <div class="apt">
          <div class="apt-ico">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="5.5" stroke="#1a3c2e" stroke-width="1.5"/><path d="M8 5.5v3l2 1.5" stroke="#1a3c2e" stroke-width="1.5" stroke-linecap="round"/></svg>
          </div>
          <div>
            <div class="apt-t">Configurable</div>
            <div class="apt-d">Articles non tag&uacute;s uniquement, ou tout le flux. De 5 &agrave; 200 articles par session.</div>
          </div>
        </div>
      </div>
    </div>

    <div class="terminal">
      <div class="tbar">
        <div class="tdot" style="background:#ff5f57"></div>
        <div class="tdot" style="background:#febc2e"></div>
        <div class="tdot" style="background:#28c840"></div>
        <span class="tlbl">Agent Curation IA &mdash; session active</span>
      </div>
      <div class="tlog" id="sc-log"></div>
      <div class="tprog"><div class="tpbar" id="sc-bar"></div></div>
      <div class="tmeta">
        <span id="sc-status">En attente&hellip;</span>
        <span id="sc-pct">0%</span>
      </div>
    </div>
  </div>
</div>

<!-- ── FOOTER ── -->
<footer>
  <div>
    <div class="flogo">SubstanCiel</div>
    <div class="ftag">Plateforme de veille intelligente &mdash; financement public</div>
  </div>
  <div class="flinks">
    <a href="/app">Espace Curation</a>
    <a href="/consultant">Espace Collecte</a>
  </div>
</footer>

<script>
(function () {
  var logs = [
    { t: 'ok',   l: 'Chargement de 47 articles non tag\u00e9s\u2026' },
    { t: 'disp', l: 'AAP ADEME Fonds Chaleur 2025 \u2192 \u2b50 Dispositif \u00b7 \u00c9nergie \u00b7 AAP \u00b7 National' },
    { t: 'act',  l: 'France 2030 bilan mi-parcours \u2192 \u2b50 Actualit\u00e9 \u00b7 Innovation \u00b7 National' },
    { t: 'del',  l: 'Supprim\u00e9 \u2014 hors sujet (presse g\u00e9n\u00e9raliste)' },
    { t: 'disp', l: 'AMI Bpifrance Industrie verte \u2192 \u2b50 Dispositif \u00b7 Industrie \u00b7 AMI' },
    { t: 'act',  l: 'PLF 2026 cr\u00e9dit imp\u00f4t recherche \u2192 \u2b50 Actualit\u00e9 \u00b7 R\u00e9forme' },
    { t: 'disp', l: 'FEADER Occitanie 2025 \u2192 \u2b50 Dispositif \u00b7 Agriculture \u00b7 FEADER' },
    { t: 'del',  l: 'Supprim\u00e9 \u2014 contenu dupliqu\u00e9 d\u00e9tect\u00e9' },
    { t: 'ok',   l: '\u2713 47 trait\u00e9s \u2014 32 tag\u00e9s \u00b7 8 supprim\u00e9s \u00b7 0 erreur' }
  ];
  var cm = { ok: 'tok', disp: 'tdisp', act: 'tact', del: 'tdel' };
  var lm = { ok: 'OK', disp: 'DISP', act: 'ACT', del: 'DEL' };
  var logEl = document.getElementById('sc-log');
  var bar   = document.getElementById('sc-bar');
  var st    = document.getElementById('sc-status');
  var pct   = document.getElementById('sc-pct');
  var s = 0;

  function next() {
    if (s >= logs.length) {
      bar.style.width = '100%';
      st.textContent  = '\u2713 Termin\u00e9';
      pct.textContent = '100%';
      setTimeout(function () {
        s = 0; logEl.innerHTML = '';
        bar.style.transition = 'none'; bar.style.width = '0%';
        st.textContent = 'En attente\u2026'; pct.textContent = '0%';
        setTimeout(function () { bar.style.transition = 'width 1s ease'; }, 50);
        setTimeout(next, 1400);
      }, 3200);
      return;
    }
    var l   = logs[s];
    var div = document.createElement('div');
    div.className = 'tline';
    div.innerHTML = '<span class="ttag ' + cm[l.t] + '">' + lm[l.t] + '</span>'
                  + '<span class="ttxt">' + l.l + '</span>';
    logEl.appendChild(div);
    while (logEl.children.length > 5) logEl.removeChild(logEl.children[0]);
    var p = Math.round((s + 1) / logs.length * 100);
    bar.style.width = p + '%';
    st.textContent  = (s + 1) + '/' + logs.length + ' articles';
    pct.textContent = p + '%';
    s++;
    setTimeout(next, s === logs.length ? 500 : 900 + Math.random() * 500);
  }
  setTimeout(next, 800);
})();
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

    # Priorite 2 : page HTML (timeout 10s)
    if not page_text:
        try:
            req_html = Request(url, headers={
                'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Accept-Language':'fr-FR,fr;q=0.9',
            })
            with urlopen(req_html, timeout=10) as resp_html:
                raw_html = resp_html.read(150000).decode('utf-8', errors='ignore')
            page_text = re.sub(r'<[^>]+>', ' ', raw_html)
            page_text = re.sub(r'\s+', ' ', page_text).strip()[:6000]
        except Exception as e:
            log.warning(f"Fetch error {url}: {e}")
            page_text = f"Titre : {title}\nURL : {url}\n(Contenu non accessible)"

    # Call Claude Haiku (timeout 25s)
    try:
        cdc_mention = f"\nCahier des charges : {pdf_url}" if pdf_url else ""
        user_content = f"Analyse ce dispositif et remplis la grille.{cdc_mention}\n\nTitre : {title}\nURL : {url}\n[Source : {source_used}]\n\nContenu :\n{page_text}"
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 1500,
            "system": COLLECT_PROMPT,
            "messages": [{"role":"user","content":user_content}]
        }).encode()
        req = Request("https://api.anthropic.com/v1/messages", data=payload, headers={
            "Content-Type":"application/json",
            "x-api-key":ANTHROPIC_API_KEY,
            "anthropic-version":"2023-06-01"
        }, method="POST")
        with urlopen(req, timeout=25) as resp:
            claude_data = json.loads(resp.read())
        text = claude_data["content"][0]["text"].strip()
        m = re.search(r'\{[\s\S]*\}', text)
        result = json.loads(m.group() if m else text)
        result['source_url'] = url
        result['article_id'] = article_id
        if pdf_url:
            result['cdc_url'] = pdf_url
        return jsonify(result)
    except Exception as e:
        log.error(f"Collect Claude error: {e}")
        return jsonify({'error': str(e)}),500


@app.route('/api/dispositifs', methods=['GET'])
def get_dispositifs():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM dispositifs ORDER BY collected_at DESC")
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
CDC_DOC_EXTENSIONS = ('.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg')

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
            elif has_kw_txt:
                candidates_txt_kw.append(abs_href)

        # Retourne le meilleur candidat par priorité
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
    init_db()
    start_scheduler()
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)))
else:
    init_db()
    start_scheduler()
