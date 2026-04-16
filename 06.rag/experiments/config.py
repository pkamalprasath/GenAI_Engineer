"""
config.py  —  Shared config, .env loading, test questions.
Run: python config.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env is one level up (rag/.env)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
PDF_PATH    = BASE_DIR.parent / "data" / "human-nutrition-text.pdf"
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ── API Keys ───────────────────────────────────────────────────────────────
CLAUDE_API_KEY  = os.getenv("CLAUDE_API_KEY", "")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
COHERE_API_KEY  = os.getenv("COHERE_API_KEY", "")

HAS_CLAUDE  = bool(CLAUDE_API_KEY)
HAS_OPENAI  = bool(OPENAI_API_KEY)
HAS_COHERE  = bool(COHERE_API_KEY)

# ── RAG defaults (same baseline as Data_ingestion.ipynb) ──────────────────
TOP_K = 5

# ── Prompt — identical to Data_ingestion.ipynb ────────────────────────────
def prompt_formatter(query: str, context_items: list[dict]) -> str:
    """
    Same prompt template used in Data_ingestion.ipynb.
    context_items: list of dicts with key 'sentence_chunk'.
    """
    context = "- " + "\n- ".join([item["sentence_chunk"] for item in context_items])
    base_prompt = f"""Based on the following context items, please answer the query.
Give yourself room to think by extracting relevant passages from the context \
before answering the query.
Don't return the thinking, only return the answer.
Make sure your answers are as explanatory as possible.
Use the following context items to answer the user query:
{context}
User query: {query}
Answer:"""
    return base_prompt

# ── Test questions (from human-nutrition-text.pdf) ────────────────────────
TEST_QUESTIONS = [
    # ── Macronutrients ────────────────────────────────────────────────────
    {
        "question": "What are the main macronutrients and their primary functions in the body?",
        "ground_truth": (
            "The main macronutrients are carbohydrates, proteins, and fats. "
            "Carbohydrates provide energy, proteins build and repair tissues, "
            "and fats provide energy storage and support cell function."
        ),
    },
    {
        "question": "What is the role of dietary fiber in human health?",
        "ground_truth": (
            "Dietary fiber aids digestion, promotes satiety, regulates blood sugar, "
            "and supports healthy gut bacteria. It helps prevent constipation and may "
            "reduce risk of heart disease and type 2 diabetes."
        ),
    },
    {
        "question": "What are essential amino acids and why are they important?",
        "ground_truth": (
            "Essential amino acids cannot be synthesized by the body and must come "
            "from food. They are critical for protein synthesis, enzyme production, "
            "and many metabolic processes."
        ),
    },
    {
        "question": "How does the body use glucose for energy?",
        "ground_truth": (
            "Glucose is broken down through glycolysis and the citric acid cycle to "
            "produce ATP. Excess glucose is stored as glycogen in the liver and muscles."
        ),
    },
    {
        "question": "What is the difference between saturated and unsaturated fats?",
        "ground_truth": (
            "Saturated fats have no double bonds and are solid at room temperature, "
            "found mainly in animal products. Unsaturated fats have one or more double "
            "bonds, are liquid at room temperature, found in plant oils and fish."
        ),
    },
    {
        "question": "What are the consequences of protein deficiency?",
        "ground_truth": (
            "Protein deficiency causes muscle wasting, impaired immune function, edema, "
            "slow wound healing, and in severe cases kwashiorkor or marasmus."
        ),
    },
    {
        "question": "What is the difference between complete and incomplete proteins?",
        "ground_truth": (
            "Complete proteins contain all nine essential amino acids in sufficient amounts "
            "and are found in animal foods. Incomplete proteins lack one or more essential "
            "amino acids and are mainly found in plant foods."
        ),
    },
    {
        "question": "How are complex carbohydrates different from simple sugars?",
        "ground_truth": (
            "Complex carbohydrates are long chains of sugar molecules (starches and fiber) "
            "that digest slowly. Simple sugars are one or two sugar units that digest "
            "quickly, causing rapid blood glucose spikes."
        ),
    },
    {
        "question": "What is the recommended daily protein intake for adults?",
        "ground_truth": (
            "The recommended dietary allowance for protein is 0.8 grams per kilogram of "
            "body weight per day for sedentary adults. Athletes and older adults may need more."
        ),
    },
    {
        "question": "What role do omega-3 fatty acids play in the body?",
        "ground_truth": (
            "Omega-3 fatty acids are essential fats that reduce inflammation, support brain "
            "function, heart health, and eye health. They are found in fatty fish, flaxseed, "
            "and walnuts."
        ),
    },
    # ── Vitamins ──────────────────────────────────────────────────────────
    {
        "question": "What are fat-soluble vitamins and what foods contain them?",
        "ground_truth": (
            "Fat-soluble vitamins are A, D, E, and K. They are found in fatty foods "
            "like liver, dairy, nuts, and oils, and require fat for absorption."
        ),
    },
    {
        "question": "How does vitamin C contribute to human health?",
        "ground_truth": (
            "Vitamin C is an antioxidant that supports immune function, collagen "
            "synthesis, iron absorption, and wound healing. Deficiency causes scurvy."
        ),
    },
    {
        "question": "What is vitamin D and why is it important?",
        "ground_truth": (
            "Vitamin D is a fat-soluble vitamin that regulates calcium absorption, supports "
            "bone health, immune function, and muscle function. It is synthesized by the skin "
            "on exposure to sunlight and found in fatty fish and fortified foods."
        ),
    },
    {
        "question": "What are the functions of B vitamins in the body?",
        "ground_truth": (
            "B vitamins (B1, B2, B3, B5, B6, B7, B9, B12) are essential for energy metabolism, "
            "red blood cell formation, DNA synthesis, and nervous system function."
        ),
    },
    {
        "question": "What causes vitamin A deficiency and what are its effects?",
        "ground_truth": (
            "Vitamin A deficiency is caused by inadequate dietary intake, especially in "
            "developing countries. It leads to night blindness, increased susceptibility "
            "to infections, and in severe cases, complete blindness (xerophthalmia)."
        ),
    },
    {
        "question": "What is folate and what happens when it is deficient?",
        "ground_truth": (
            "Folate (vitamin B9) is essential for DNA synthesis and cell division. Deficiency "
            "during pregnancy causes neural tube defects in the developing fetus. It also "
            "leads to megaloblastic anemia."
        ),
    },
    {
        "question": "What is vitamin K and what role does it play?",
        "ground_truth": (
            "Vitamin K is essential for blood clotting and bone metabolism. It activates "
            "proteins needed for coagulation and helps incorporate calcium into bones."
        ),
    },
    {
        "question": "What are water-soluble vitamins and how do they differ from fat-soluble ones?",
        "ground_truth": (
            "Water-soluble vitamins (C and B vitamins) dissolve in water, are not stored "
            "in the body, and excess is excreted in urine. Fat-soluble vitamins (A, D, E, K) "
            "are stored in fat tissue and can accumulate to toxic levels."
        ),
    },
    # ── Minerals ──────────────────────────────────────────────────────────
    {
        "question": "What are the functions of minerals like calcium and iron in the body?",
        "ground_truth": (
            "Calcium is essential for bone and teeth formation, muscle contraction, "
            "and nerve signaling. Iron is needed for hemoglobin to transport oxygen."
        ),
    },
    {
        "question": "What is the role of sodium in the body and what are the risks of excess intake?",
        "ground_truth": (
            "Sodium maintains fluid balance, nerve transmission, and muscle function. "
            "Excess sodium intake raises blood pressure and increases the risk of "
            "cardiovascular disease and stroke."
        ),
    },
    {
        "question": "What foods are rich in calcium and why is calcium important?",
        "ground_truth": (
            "Calcium-rich foods include dairy products, leafy greens, fortified foods, and "
            "almonds. Calcium is vital for bone density, muscle contraction, and nerve function. "
            "Deficiency leads to osteoporosis."
        ),
    },
    {
        "question": "What is zinc and what is its role in human nutrition?",
        "ground_truth": (
            "Zinc is a trace mineral essential for immune function, wound healing, protein "
            "synthesis, DNA synthesis, and taste and smell. Deficiency causes growth "
            "retardation, immune dysfunction, and delayed wound healing."
        ),
    },
    {
        "question": "What is the function of magnesium in the human body?",
        "ground_truth": (
            "Magnesium is involved in over 300 enzymatic reactions, energy production, "
            "protein synthesis, muscle and nerve function, blood glucose control, and "
            "blood pressure regulation."
        ),
    },
    {
        "question": "What is iodine deficiency and what are its consequences?",
        "ground_truth": (
            "Iodine deficiency impairs thyroid hormone production, leading to goiter, "
            "hypothyroidism, and in pregnant women, cretinism and intellectual disability "
            "in the child."
        ),
    },
    # ── Digestion and Metabolism ──────────────────────────────────────────
    {
        "question": "How does saliva help with digestion?",
        "ground_truth": (
            "Saliva moistens food for easier swallowing, contains amylase to begin starch "
            "digestion, and contains lysozyme for antibacterial protection."
        ),
    },
    {
        "question": "What is the glycemic index and why does it matter?",
        "ground_truth": (
            "The glycemic index measures how quickly a food raises blood glucose. "
            "Low-GI foods cause slower blood sugar rises, important for managing "
            "diabetes and maintaining stable energy levels."
        ),
    },
    {
        "question": "How does the small intestine absorb nutrients?",
        "ground_truth": (
            "The small intestine absorbs nutrients through villi and microvilli that increase "
            "surface area. Nutrients pass into the bloodstream via active transport and "
            "diffusion; fats are absorbed into the lymphatic system via lacteals."
        ),
    },
    {
        "question": "What is basal metabolic rate and what factors affect it?",
        "ground_truth": (
            "Basal metabolic rate is the energy the body needs at rest to maintain basic "
            "functions. It is affected by age, sex, body composition, genetics, hormones, "
            "and nutritional status."
        ),
    },
    {
        "question": "What is the role of the liver in nutrient metabolism?",
        "ground_truth": (
            "The liver processes absorbed nutrients, synthesizes proteins, produces bile for "
            "fat digestion, stores glycogen, performs gluconeogenesis, and detoxifies harmful "
            "substances."
        ),
    },
    {
        "question": "How does insulin regulate blood glucose levels?",
        "ground_truth": (
            "Insulin is released by the pancreas in response to high blood glucose. It "
            "promotes glucose uptake by cells, glycogen synthesis in the liver and muscles, "
            "and fat storage, lowering blood glucose levels."
        ),
    },
    {
        "question": "What happens to excess energy from food in the body?",
        "ground_truth": (
            "Excess energy is stored as glycogen in the liver and muscles, and when those "
            "stores are full, it is converted to fat and stored in adipose tissue."
        ),
    },
    {
        "question": "What is gluconeogenesis and when does the body use it?",
        "ground_truth": (
            "Gluconeogenesis is the synthesis of glucose from non-carbohydrate precursors "
            "such as amino acids, lactate, and glycerol. It occurs mainly in the liver "
            "during fasting or prolonged exercise when blood glucose is low."
        ),
    },
    {
        "question": "How does the stomach contribute to digestion?",
        "ground_truth": (
            "The stomach churns food into chyme, secretes hydrochloric acid to kill bacteria "
            "and activate pepsin, and releases pepsinogen which digests proteins. It also "
            "secretes intrinsic factor for vitamin B12 absorption."
        ),
    },
    # ── Energy Balance and Weight ─────────────────────────────────────────
    {
        "question": "What is energy balance and how does it relate to body weight?",
        "ground_truth": (
            "Energy balance is the relationship between energy intake from food and energy "
            "expenditure. Positive balance (more in than out) leads to weight gain; negative "
            "balance leads to weight loss."
        ),
    },
    {
        "question": "What are the health risks associated with obesity?",
        "ground_truth": (
            "Obesity increases the risk of type 2 diabetes, cardiovascular disease, "
            "hypertension, certain cancers, sleep apnea, joint problems, and reduced "
            "life expectancy."
        ),
    },
    {
        "question": "What is the body mass index and what are its limitations?",
        "ground_truth": (
            "BMI is weight in kilograms divided by height in meters squared. While used "
            "to classify weight status, it does not measure body fat directly and can "
            "misclassify muscular individuals or underestimate fat in older adults."
        ),
    },
    {
        "question": "How does physical activity affect nutritional requirements?",
        "ground_truth": (
            "Physical activity increases energy needs, protein requirements for muscle "
            "repair, fluid needs due to sweat, and micronutrient needs for energy "
            "metabolism and tissue repair."
        ),
    },
    # ── Special Diets and Conditions ──────────────────────────────────────
    {
        "question": "What are the nutritional considerations for a vegetarian or vegan diet?",
        "ground_truth": (
            "Vegetarians and vegans must carefully plan to get sufficient protein, vitamin B12, "
            "iron, calcium, zinc, omega-3 fatty acids, and vitamin D, which are less abundant "
            "or less bioavailable in plant foods."
        ),
    },
    {
        "question": "What is malnutrition and what are its main forms?",
        "ground_truth": (
            "Malnutrition includes undernutrition (inadequate calories or nutrients), "
            "overnutrition (excess intake), and micronutrient deficiencies. It impairs "
            "growth, immunity, cognitive function, and organ function."
        ),
    },
    {
        "question": "What dietary changes are recommended for managing type 2 diabetes?",
        "ground_truth": (
            "Managing type 2 diabetes involves controlling carbohydrate intake, choosing "
            "low-GI foods, increasing fiber, reducing saturated fat, maintaining healthy "
            "weight, and monitoring portion sizes."
        ),
    },
    {
        "question": "What is celiac disease and what dietary restrictions does it require?",
        "ground_truth": (
            "Celiac disease is an autoimmune condition triggered by gluten, a protein in "
            "wheat, barley, and rye. It requires a strict lifelong gluten-free diet to "
            "prevent intestinal damage."
        ),
    },
    {
        "question": "What nutritional needs are unique to pregnant women?",
        "ground_truth": (
            "Pregnant women need increased folate to prevent neural tube defects, iron for "
            "fetal blood production, calcium for fetal bones, iodine for brain development, "
            "and additional calories and protein for fetal growth."
        ),
    },
    {
        "question": "How do nutritional needs change as people age?",
        "ground_truth": (
            "Older adults need fewer calories due to reduced metabolic rate and physical "
            "activity, but require more calcium, vitamin D, and B12. Protein needs remain "
            "high to prevent muscle loss (sarcopenia)."
        ),
    },
    # ── Food and Health ───────────────────────────────────────────────────
    {
        "question": "What is the Mediterranean diet and what are its health benefits?",
        "ground_truth": (
            "The Mediterranean diet emphasizes fruits, vegetables, whole grains, legumes, "
            "nuts, olive oil, and fish. It is associated with reduced cardiovascular disease, "
            "lower cancer risk, and better cognitive health."
        ),
    },
    {
        "question": "What are antioxidants and what role do they play in health?",
        "ground_truth": (
            "Antioxidants neutralize free radicals that damage cells. They include vitamins "
            "C and E, beta-carotene, and selenium. They help prevent oxidative stress linked "
            "to cancer, heart disease, and aging."
        ),
    },
    {
        "question": "What is the role of water in human nutrition?",
        "ground_truth": (
            "Water is essential for temperature regulation, nutrient transport, digestion, "
            "joint lubrication, and waste elimination. The body is about 60% water and must "
            "maintain hydration for all physiological processes."
        ),
    },
    {
        "question": "What are phytochemicals and why are they important?",
        "ground_truth": (
            "Phytochemicals are biologically active compounds in plants such as flavonoids, "
            "carotenoids, and polyphenols. They have antioxidant, anti-inflammatory, and "
            "potentially anticancer properties."
        ),
    },
    {
        "question": "What is the difference between food security and food insecurity?",
        "ground_truth": (
            "Food security means reliable access to sufficient, safe, and nutritious food. "
            "Food insecurity is the lack of consistent access, leading to hunger, poor "
            "nutrition, and health consequences."
        ),
    },
    {
        "question": "How does food processing affect the nutritional value of food?",
        "ground_truth": (
            "Processing can remove fiber, vitamins, and minerals while adding sodium, "
            "sugar, and unhealthy fats. However, some processing (fortification, cooking) "
            "can improve nutritional value or bioavailability."
        ),
    },
    {
        "question": "What is cholesterol and how does diet affect blood cholesterol levels?",
        "ground_truth": (
            "Cholesterol is a lipid needed for cell membranes and hormone production. "
            "Saturated and trans fats raise LDL cholesterol; unsaturated fats and fiber "
            "can lower it. High LDL increases cardiovascular disease risk."
        ),
    },
    {
        "question": "What is the function of bile in digestion?",
        "ground_truth": (
            "Bile, produced by the liver and stored in the gallbladder, emulsifies dietary "
            "fats into smaller droplets so lipase can digest them more efficiently. It also "
            "aids absorption of fat-soluble vitamins."
        ),
    },
    {
        "question": "What is the gut microbiome and how does diet influence it?",
        "ground_truth": (
            "The gut microbiome is the community of trillions of microorganisms in the "
            "intestine. Diet shapes its composition; fiber and fermented foods promote "
            "beneficial bacteria, while highly processed diets can disrupt it."
        ),
    },
    {
        "question": "What are trans fats and why are they harmful?",
        "ground_truth": (
            "Trans fats are partially hydrogenated vegetable oils found in some processed "
            "foods. They raise LDL (bad) cholesterol, lower HDL (good) cholesterol, and "
            "significantly increase the risk of heart disease."
        ),
    },
    {
        "question": "What is the difference between hunger and appetite?",
        "ground_truth": (
            "Hunger is a physiological drive to eat triggered by energy depletion and "
            "hormones like ghrelin. Appetite is the psychological desire to eat, influenced "
            "by sensory cues, emotions, and learned behaviors."
        ),
    },
    {
        "question": "What is the role of iron in the body and what causes iron deficiency anemia?",
        "ground_truth": (
            "Iron is a component of hemoglobin that carries oxygen in red blood cells. "
            "Iron deficiency anemia occurs when iron stores are depleted, reducing red blood "
            "cell production and causing fatigue, pallor, and weakness."
        ),
    },
    {
        "question": "How does dehydration affect physical and cognitive performance?",
        "ground_truth": (
            "Even mild dehydration (1-2% body weight) impairs concentration, memory, and "
            "mood. Greater dehydration reduces physical endurance, increases heart rate, "
            "and impairs temperature regulation."
        ),
    },
    {
        "question": "What are the dietary sources and health effects of potassium?",
        "ground_truth": (
            "Potassium is found in bananas, potatoes, leafy greens, and legumes. It "
            "maintains fluid balance, nerve function, and muscle contraction, and helps "
            "counteract the blood-pressure-raising effects of sodium."
        ),
    },
]


if __name__ == "__main__":
    print("=" * 60)
    print("RAG Experiment Suite -- Config Check")
    print("=" * 60)
    print(f"PDF path    : {PDF_PATH}")
    print(f"PDF exists  : {PDF_PATH.exists()}")
    print(f"Results dir : {RESULTS_DIR}")
    print(f"Claude key  : {'SET' if HAS_CLAUDE else 'MISSING'}")
    print(f"OpenAI key  : {'SET' if HAS_OPENAI else 'not set'}")
    print(f"Cohere key  : {'SET' if HAS_COHERE else 'not set (optional)'}")
    print(f"\nTest questions: {len(TEST_QUESTIONS)}")
    for i, q in enumerate(TEST_QUESTIONS, 1):
        print(f"  Q{i:02d}: {q['question'][:70]}")
    print("\n[OK] Config ready" if PDF_PATH.exists() else "\n[FAIL] PDF not found")
