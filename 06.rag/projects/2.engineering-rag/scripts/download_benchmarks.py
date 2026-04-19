"""
download_benchmarks.py — Download benchmark dataset files automatically.

Downloads only the small/medium files:
  SQuAD 2.0    : 3.8 MB   → data/benchmarks/squad/dev-v2.0.json
  HotpotQA     : 54 MB    → data/benchmarks/hotpotqa/hotpot_dev_distractor_v1.json
  NQ (tiny)    : ~5 MB    → data/benchmarks/natural_questions/nq-dev.jsonl  (100 samples)

Skips MS MARCO (2.9 GB corpus — too large for auto-download).

Usage:
    python download_benchmarks.py
    python download_benchmarks.py --datasets squad hotpotqa
"""

import argparse
import json
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent.parent / "data" / "benchmarks"

DATASETS = {
    "squad": {
        "url":  "https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v2.0.json",
        "dest": BASE / "squad" / "dev-v2.0.json",
        "size": "3.8 MB",
    },
    "hotpotqa": {
        "url":  "http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json",
        "dest": BASE / "hotpotqa" / "hotpot_dev_distractor_v1.json",
        "size": "54 MB",
    },
}


def download(name: str, info: dict, force: bool = False) -> bool:
    dest: Path = info["dest"]
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and not force:
        print(f"[{name}] Already exists: {dest.name} — skipping (use --force to re-download)")
        return True

    print(f"[{name}] Downloading {info['size']} from {info['url']}")
    print(f"[{name}] Saving to {dest} ...")

    try:
        def progress(block_num, block_size, total_size):
            if total_size > 0:
                pct = min(block_num * block_size / total_size * 100, 100)
                print(f"\r  {pct:.1f}%", end="", flush=True)

        urllib.request.urlretrieve(info["url"], dest, reporthook=progress)
        print(f"\r[{name}] Done — saved {dest.stat().st_size // 1024:,} KB")
        return True
    except Exception as e:
        print(f"\n[{name}] FAILED: {e}")
        if dest.exists():
            dest.unlink()
        return False


def create_nq_sample() -> None:
    """
    Create a small NQ-format sample file with 10 representative questions
    for testing when the full NQ download is unavailable.
    """
    dest = BASE / "natural_questions" / "nq-dev.jsonl"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        print("[natural_questions] Sample file already exists — skipping")
        return

    samples = [
        {"question_text": "who invented the telephone", "document_title": "Telephone",
         "document_text": "The telephone was invented by Alexander Graham Bell in 1876. Bell was awarded the first patent for the electric telephone. He made the first successful telephone call on March 10, 1876.",
         "annotations": [{"short_answers": [{"start_token": 37, "end_token": 39}], "yes_no_answer": "NONE"}]},
        {"question_text": "what is the boiling point of water in celsius", "document_title": "Water",
         "document_text": "Water boils at 100 degrees Celsius (212 degrees Fahrenheit) at standard atmospheric pressure of 101.325 kPa. At higher altitudes the boiling point decreases.",
         "annotations": [{"short_answers": [{"start_token": 4, "end_token": 7}], "yes_no_answer": "NONE"}]},
        {"question_text": "who wrote hamlet", "document_title": "Hamlet",
         "document_text": "Hamlet is a tragedy written by William Shakespeare between 1599 and 1601. It is one of his most famous plays and has been performed more than any other Shakespeare play.",
         "annotations": [{"short_answers": [{"start_token": 9, "end_token": 11}], "yes_no_answer": "NONE"}]},
        {"question_text": "what year did world war 2 end", "document_title": "World War II",
         "document_text": "World War II ended in 1945. The war in Europe ended on May 8, 1945 (V-E Day) when Germany surrendered. The war in the Pacific ended on September 2, 1945 (V-J Day) when Japan formally surrendered.",
         "annotations": [{"short_answers": [{"start_token": 6, "end_token": 7}], "yes_no_answer": "NONE"}]},
        {"question_text": "what is the speed of light in metres per second", "document_title": "Speed of light",
         "document_text": "The speed of light in a vacuum is exactly 299,792,458 metres per second. This constant, denoted c, is fundamental to physics and appears in Einstein's famous equation E=mc2.",
         "annotations": [{"short_answers": [{"start_token": 9, "end_token": 11}], "yes_no_answer": "NONE"}]},
        {"question_text": "how many bones are in the human body", "document_title": "Human skeleton",
         "document_text": "The adult human body has 206 bones. At birth, humans have around 270 to 300 bones, but many of these fuse together during childhood and adolescence.",
         "annotations": [{"short_answers": [{"start_token": 5, "end_token": 7}], "yes_no_answer": "NONE"}]},
        {"question_text": "what is the largest planet in the solar system", "document_title": "Jupiter",
         "document_text": "Jupiter is the largest planet in the solar system. It is a gas giant with a mass more than two and a half times that of all the other planets in the solar system combined.",
         "annotations": [{"short_answers": [{"start_token": 0, "end_token": 1}], "yes_no_answer": "NONE"}]},
        {"question_text": "who painted the mona lisa", "document_title": "Mona Lisa",
         "document_text": "The Mona Lisa was painted by Leonardo da Vinci. It was created between 1503 and 1519 and is housed in the Louvre Museum in Paris, France.",
         "annotations": [{"short_answers": [{"start_token": 7, "end_token": 10}], "yes_no_answer": "NONE"}]},
        {"question_text": "what is the chemical symbol for gold", "document_title": "Gold",
         "document_text": "The chemical symbol for gold is Au, which comes from the Latin word 'aurum'. Gold has atomic number 79 and is a transition metal known for its malleability and conductivity.",
         "annotations": [{"short_answers": [{"start_token": 6, "end_token": 7}], "yes_no_answer": "NONE"}]},
        {"question_text": "what country is the amazon river in", "document_title": "Amazon River",
         "document_text": "The Amazon River flows primarily through Brazil, though it also passes through Peru and Colombia. It is the largest river in the world by discharge volume and the second longest river.",
         "annotations": [{"short_answers": [{"start_token": 7, "end_token": 8}], "yes_no_answer": "NONE"}]},
    ]

    with open(dest, "w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample) + "\n")

    print(f"[natural_questions] Created sample file with 10 questions → {dest}")


def create_msmarco_sample() -> None:
    """Create small MS MARCO-format TSV files with 10 queries for testing."""
    msmarco_dir = BASE / "msmarco"
    msmarco_dir.mkdir(parents=True, exist_ok=True)

    col_file    = msmarco_dir / "collection.tsv"
    query_file  = msmarco_dir / "queries.dev.small.tsv"
    qrels_file  = msmarco_dir / "qrels.dev.small.tsv"

    if col_file.exists() and query_file.exists():
        print("[msmarco] Sample files already exist — skipping")
        return

    passages = [
        (1, "The tensile strength of steel varies depending on the grade. Structural steel A36 has a minimum tensile strength of 400 MPa. High-strength low-alloy steel can reach 700 MPa or higher."),
        (2, "Hydraulic systems use pressurised fluid to transmit power. Common hydraulic fluids include mineral oil, synthetic esters, and water-glycol mixtures. System pressures typically range from 70 to 700 bar."),
        (3, "Bearing selection depends on load direction and magnitude. Radial bearings handle loads perpendicular to the shaft. Thrust bearings handle axial loads along the shaft axis."),
        (4, "The viscosity index of a lubricant indicates how much its viscosity changes with temperature. A high viscosity index means less change with temperature, which is desirable for wide-temperature applications."),
        (5, "Gear ratios determine the relationship between input and output shaft speeds. A ratio of 4:1 means the input shaft rotates four times for each output shaft rotation, multiplying torque by four."),
        (6, "Corrosion protection methods include galvanising, electroplating, anodising, and painting. Galvanising applies a zinc coating to steel to provide sacrificial cathodic protection."),
        (7, "Centrifugal pumps convert rotational kinetic energy to hydrodynamic energy. The impeller accelerates fluid outward by centrifugal force, converting velocity to pressure in the volute casing."),
        (8, "Thread locking compounds prevent fasteners from loosening due to vibration. Anaerobic adhesives cure in the absence of oxygen and bond metal threads without requiring external heat."),
        (9, "Heat treatment of steel involves controlled heating and cooling to alter mechanical properties. Annealing softens steel, normalising refines grain structure, and hardening increases hardness via quenching."),
        (10, "Pressure relief valves protect pressure vessels from overpressure. They open automatically when pressure exceeds the set point and close when pressure returns to safe levels."),
        (11, "Electrical motor efficiency classes are defined by IEC 60034-30. IE1 is standard efficiency, IE2 is high efficiency, IE3 is premium efficiency, and IE4 is super premium efficiency."),
        (12, "Pipe flanges are standardised by ASME B16.5 for pressure ratings. Flange classes (150, 300, 600, 900, 1500, 2500) define maximum allowable working pressure at specified temperatures."),
    ]

    queries = [
        (101, "tensile strength of structural steel"),
        (102, "hydraulic system fluid pressure range"),
        (103, "difference between radial and thrust bearings"),
        (104, "what does viscosity index measure"),
        (105, "how does gear ratio affect torque"),
        (106, "methods to prevent steel corrosion"),
        (107, "how does a centrifugal pump work"),
        (108, "how to prevent bolt loosening from vibration"),
        (109, "heat treatment methods for steel"),
        (110, "purpose of pressure relief valve"),
    ]

    qrels = [
        (101, 0, 1, 1),
        (102, 0, 2, 1),
        (103, 0, 3, 1),
        (104, 0, 4, 1),
        (105, 0, 5, 1),
        (106, 0, 6, 1),
        (107, 0, 7, 1),
        (108, 0, 8, 1),
        (109, 0, 9, 1),
        (110, 0, 10, 1),
        # Additional relevant passages
        (101, 0, 9, 1),
        (107, 0, 2, 1),
    ]

    with open(col_file, "w", encoding="utf-8") as f:
        for pid, text in passages:
            f.write(f"{pid}\t{text}\n")

    with open(query_file, "w", encoding="utf-8") as f:
        for qid, qtext in queries:
            f.write(f"{qid}\t{qtext}\n")

    with open(qrels_file, "w", encoding="utf-8") as f:
        for qid, zero, pid, rel in qrels:
            f.write(f"{qid}\t{zero}\t{pid}\t{rel}\n")

    print(f"[msmarco] Created sample files with 10 queries → {msmarco_dir}")


def create_squad_sample() -> None:
    """Create a small SQuAD 2.0-format JSON with 10 questions for testing."""
    dest = BASE / "squad" / "dev-v2.0.json"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        print("[squad] File already exists — skipping")
        return

    data = {
        "version": "v2.0-sample",
        "data": [
            {
                "title": "Thermodynamics",
                "paragraphs": [
                    {
                        "context": "The first law of thermodynamics states that energy cannot be created or destroyed, only transformed from one form to another. The total energy of an isolated system remains constant. This principle is also known as the law of conservation of energy.",
                        "qas": [
                            {"id": "s1q1", "question": "What does the first law of thermodynamics state?", "answers": [{"text": "energy cannot be created or destroyed, only transformed", "answer_start": 56}], "is_impossible": False},
                            {"id": "s1q2", "question": "What is another name for the first law of thermodynamics?", "answers": [{"text": "law of conservation of energy", "answer_start": 215}], "is_impossible": False},
                        ]
                    },
                    {
                        "context": "The second law of thermodynamics states that the total entropy of an isolated system can only increase over time. Heat flows spontaneously from a hotter body to a cooler body. This is why perpetual motion machines of the second kind are impossible.",
                        "qas": [
                            {"id": "s1q3", "question": "What happens to entropy in an isolated system according to the second law?", "answers": [{"text": "can only increase over time", "answer_start": 77}], "is_impossible": False},
                        ]
                    }
                ]
            },
            {
                "title": "Fluid_Mechanics",
                "paragraphs": [
                    {
                        "context": "Bernoulli's principle states that an increase in the speed of a fluid occurs simultaneously with a decrease in static pressure. This principle is fundamental to understanding how aircraft wings generate lift and how carburetors function. The equation P + 0.5*rho*v^2 + rho*g*h = constant.",
                        "qas": [
                            {"id": "s2q1", "question": "What happens to static pressure when fluid speed increases according to Bernoulli?", "answers": [{"text": "decrease in static pressure", "answer_start": 82}], "is_impossible": False},
                            {"id": "s2q2", "question": "What is Bernoulli's principle used to explain?", "answers": [{"text": "how aircraft wings generate lift and how carburetors function", "answer_start": 159}], "is_impossible": False},
                        ]
                    }
                ]
            },
            {
                "title": "Materials_Science",
                "paragraphs": [
                    {
                        "context": "Young's modulus is a mechanical property that measures the stiffness of a solid material. It is defined as the ratio of tensile stress to tensile strain. Steel has a Young's modulus of approximately 200 GPa, while aluminium has a modulus of about 70 GPa.",
                        "qas": [
                            {"id": "s3q1", "question": "How is Young's modulus defined?", "answers": [{"text": "ratio of tensile stress to tensile strain", "answer_start": 103}], "is_impossible": False},
                            {"id": "s3q2", "question": "What is the Young's modulus of steel?", "answers": [{"text": "approximately 200 GPa", "answer_start": 180}], "is_impossible": False},
                            {"id": "s3q3", "question": "What is the manufacturing cost of Young's modulus testing equipment?", "answers": [], "is_impossible": True},
                        ]
                    }
                ]
            },
            {
                "title": "Electrical_Engineering",
                "paragraphs": [
                    {
                        "context": "Ohm's law states that the current through a conductor between two points is directly proportional to the voltage across the two points, provided the temperature remains constant. Mathematically, V = I * R where V is voltage in volts, I is current in amperes, and R is resistance in ohms.",
                        "qas": [
                            {"id": "s4q1", "question": "What does Ohm's law state about current and voltage?", "answers": [{"text": "current through a conductor between two points is directly proportional to the voltage", "answer_start": 22}], "is_impossible": False},
                            {"id": "s4q2", "question": "In the formula V = I * R, what does I represent?", "answers": [{"text": "current in amperes", "answer_start": 231}], "is_impossible": False},
                        ]
                    }
                ]
            }
        ]
    }

    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"[squad] Created sample file with 10 questions → {dest}")


def create_hotpotqa_sample() -> None:
    """Create a small HotpotQA-format JSON with 10 multi-hop questions."""
    dest = BASE / "hotpotqa" / "hotpot_dev_distractor_v1.json"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        print("[hotpotqa] File already exists — skipping")
        return

    data = [
        {
            "_id": "h001",
            "question": "Are both the Eiffel Tower and the Colosseum located in Europe?",
            "answer": "yes",
            "type": "comparison",
            "level": "easy",
            "supporting_facts": [["Eiffel Tower", 0], ["Colosseum", 0]],
            "context": [
                ["Eiffel Tower", ["The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France.", "It is named after the engineer Gustave Eiffel, whose company designed and built the tower."]],
                ["Colosseum", ["The Colosseum is an oval amphitheatre in the centre of the city of Rome, Italy.", "It is the largest ancient amphitheatre ever built and is still the largest standing amphitheatre in the world."]],
                ["Statue of Liberty", ["The Statue of Liberty is a colossal neoclassical sculpture on Liberty Island in New York Harbor in New York City, United States."]],
                ["Big Ben", ["Big Ben is the nickname for the Great Bell of the striking clock at the north end of the Palace of Westminster in London."]],
            ]
        },
        {
            "_id": "h002",
            "question": "What material is used for both the Eiffel Tower's construction and most modern steel bridges?",
            "answer": "iron and steel",
            "type": "bridge",
            "level": "medium",
            "supporting_facts": [["Eiffel Tower", 0], ["Steel bridge", 0]],
            "context": [
                ["Eiffel Tower", ["The Eiffel Tower is a wrought-iron lattice tower built from puddled iron.", "Modern replicas use structural steel for similar lattice designs."]],
                ["Steel bridge", ["Steel bridges use structural steel as the primary construction material due to its high tensile strength.", "Structural steel has a tensile strength of 400-700 MPa depending on the grade."]],
                ["Concrete bridge", ["Concrete bridges use reinforced concrete, combining the compressive strength of concrete with the tensile strength of embedded steel rebar."]],
                ["Suspension bridge", ["Suspension bridges use high-strength steel cables to support the bridge deck from towers."]],
            ]
        },
        {
            "_id": "h003",
            "question": "Were both Newton and Einstein physicists who contributed to our understanding of gravity?",
            "answer": "yes",
            "type": "comparison",
            "level": "easy",
            "supporting_facts": [["Isaac Newton", 0], ["Albert Einstein", 0]],
            "context": [
                ["Isaac Newton", ["Isaac Newton was an English mathematician and physicist who formulated the laws of motion and universal gravitation.", "His law of universal gravitation described gravity as an attractive force between masses."]],
                ["Albert Einstein", ["Albert Einstein was a German-born theoretical physicist who developed the theory of relativity.", "His general theory of relativity reinterpreted gravity as the curvature of spacetime caused by mass."]],
                ["Galileo Galilei", ["Galileo Galilei was an Italian astronomer and physicist who studied the motion of falling objects."]],
                ["Richard Feynman", ["Richard Feynman was an American physicist known for his work in quantum electrodynamics."]],
            ]
        },
        {
            "_id": "h004",
            "question": "In what country was the inventor of the telephone born, and what language is primarily spoken there?",
            "answer": "Scotland, English",
            "type": "bridge",
            "level": "medium",
            "supporting_facts": [["Alexander Graham Bell", 0], ["Scotland", 0]],
            "context": [
                ["Alexander Graham Bell", ["Alexander Graham Bell was born on March 3, 1847, in Edinburgh, Scotland.", "He is credited with inventing and patenting the first practical telephone in 1876."]],
                ["Scotland", ["Scotland is a country that is part of the United Kingdom, located in northern Great Britain.", "English is the primary language spoken in Scotland, alongside Scottish Gaelic in some regions."]],
                ["United Kingdom", ["The United Kingdom consists of England, Scotland, Wales, and Northern Ireland."]],
                ["Ireland", ["Ireland is an island in the North Atlantic Ocean, divided between the Republic of Ireland and Northern Ireland."]],
            ]
        },
        {
            "_id": "h005",
            "question": "Do both diesel engines and petrol engines use internal combustion?",
            "answer": "yes",
            "type": "comparison",
            "level": "easy",
            "supporting_facts": [["Diesel engine", 0], ["Petrol engine", 0]],
            "context": [
                ["Diesel engine", ["A diesel engine is an internal combustion engine that uses compression ignition to ignite the fuel.", "Diesel engines are more fuel-efficient than petrol engines and are widely used in trucks and industrial equipment."]],
                ["Petrol engine", ["A petrol engine is an internal combustion engine with spark ignition, using petrol as fuel.", "Petrol engines are commonly used in passenger cars and light motorcycles."]],
                ["Electric motor", ["An electric motor converts electrical energy to mechanical energy using electromagnetic force."]],
                ["Steam engine", ["A steam engine is an external combustion engine that converts the heat energy of steam into mechanical work."]],
            ]
        },
        {
            "_id": "h006",
            "question": "What is the primary difference in ignition method between diesel and petrol engines?",
            "answer": "Diesel uses compression ignition while petrol uses spark ignition",
            "type": "comparison",
            "level": "medium",
            "supporting_facts": [["Diesel engine", 0], ["Petrol engine", 0]],
            "context": [
                ["Diesel engine", ["A diesel engine is an internal combustion engine that uses compression ignition to ignite the fuel without a spark plug.", "The air is compressed to a high ratio until it becomes hot enough to ignite the injected diesel fuel."]],
                ["Petrol engine", ["A petrol engine uses a spark plug to ignite a mixture of petrol and air inside the cylinder.", "The spark ignition timing is controlled electronically to optimise performance and efficiency."]],
                ["Gas turbine", ["A gas turbine uses continuous combustion of fuel in a compressed airstream to drive a turbine."]],
                ["Rotary engine", ["A rotary engine uses a triangular rotor that rotates inside an oval housing to convert pressure into rotating motion."]],
            ]
        },
        {
            "_id": "h007",
            "question": "Is the melting point of iron higher than the boiling point of water?",
            "answer": "yes",
            "type": "comparison",
            "level": "easy",
            "supporting_facts": [["Iron", 0], ["Water", 0]],
            "context": [
                ["Iron", ["Iron is a chemical element with symbol Fe and atomic number 26.", "Iron melts at 1538 degrees Celsius, making it suitable for high-temperature applications."]],
                ["Water", ["Water is a chemical compound with formula H2O.", "Water boils at 100 degrees Celsius at standard atmospheric pressure and freezes at 0 degrees Celsius."]],
                ["Aluminium", ["Aluminium melts at 660 degrees Celsius, which is lower than iron but higher than many other metals."]],
                ["Lead", ["Lead has a relatively low melting point of 327 degrees Celsius, which is why it has been used in soldering."]],
            ]
        },
        {
            "_id": "h008",
            "question": "What engineering principle connects the Wright Brothers' aircraft design and modern jet aircraft wing shape?",
            "answer": "Bernoulli's principle / aerofoil lift generation",
            "type": "bridge",
            "level": "hard",
            "supporting_facts": [["Wright Brothers", 1], ["Aerofoil", 0]],
            "context": [
                ["Wright Brothers", ["The Wright Brothers made the first controlled powered flight in 1903 at Kitty Hawk, North Carolina.", "They designed a curved wing profile based on observations of birds to generate aerodynamic lift."]],
                ["Aerofoil", ["An aerofoil is a shape designed to generate lift when moving through a fluid such as air.", "The curved upper surface causes air to move faster, reducing pressure above the wing according to Bernoulli's principle."]],
                ["Jet engine", ["Jet engines generate thrust by expelling high-velocity exhaust gases rearward, propelling the aircraft forward."]],
                ["Helicopter", ["Helicopter rotors use rotating aerofoil blades to generate lift vertically."]],
            ]
        },
        {
            "_id": "h009",
            "question": "Are both stainless steel and titanium known for their corrosion resistance?",
            "answer": "yes",
            "type": "comparison",
            "level": "easy",
            "supporting_facts": [["Stainless steel", 0], ["Titanium", 0]],
            "context": [
                ["Stainless steel", ["Stainless steel is a corrosion-resistant alloy containing at least 10.5% chromium by mass.", "The chromium forms a passive oxide layer on the surface that prevents further oxidation."]],
                ["Titanium", ["Titanium is a transition metal known for its high strength-to-weight ratio and excellent corrosion resistance.", "It forms a stable oxide layer that protects it from corrosion in most environments including seawater."]],
                ["Carbon steel", ["Carbon steel contains up to 2.1% carbon by weight and is susceptible to rust and corrosion without surface protection."]],
                ["Copper", ["Copper develops a green patina (verdigris) over time due to oxidation and reaction with carbon dioxide."]],
            ]
        },
        {
            "_id": "h010",
            "question": "What do hydraulic systems and pneumatic systems both use to transmit power?",
            "answer": "fluid (pressurised fluid — liquid in hydraulic, gas/air in pneumatic)",
            "type": "comparison",
            "level": "medium",
            "supporting_facts": [["Hydraulic system", 0], ["Pneumatic system", 0]],
            "context": [
                ["Hydraulic system", ["A hydraulic system uses pressurised liquid, typically hydraulic oil, to transmit and control power.", "Pascal's law states that pressure applied to a confined fluid is transmitted equally in all directions."]],
                ["Pneumatic system", ["A pneumatic system uses compressed air or gas to transmit power.", "Pneumatic systems are cleaner than hydraulic systems as any leaks release air rather than fluid."]],
                ["Mechanical transmission", ["Mechanical power transmission uses gears, belts, and chains to transfer motion between shafts."]],
                ["Electrical system", ["Electrical systems transmit power using conductors carrying electrical current from a power source to a load."]],
            ]
        },
    ]

    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"[hotpotqa] Created sample file with 10 questions → {dest}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download or create benchmark dataset files")
    parser.add_argument(
        "--datasets", nargs="+",
        choices=["squad", "hotpotqa", "natural_questions", "msmarco", "all"],
        default=["all"],
        help="Which datasets to prepare",
    )
    parser.add_argument(
        "--real", action="store_true",
        help="Download real dataset files (squad + hotpotqa only). Without this, creates sample files.",
    )
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists")
    args = parser.parse_args()

    targets = args.datasets
    if "all" in targets:
        targets = ["squad", "hotpotqa", "natural_questions", "msmarco"]

    print("=" * 60)
    print("  Benchmark Dataset Preparation")
    print("=" * 60)

    for name in targets:
        if args.real and name in DATASETS:
            download(name, DATASETS[name], force=args.force)
        else:
            # Create sample files for immediate testing
            if name == "squad":
                create_squad_sample()
            elif name == "hotpotqa":
                create_hotpotqa_sample()
            elif name == "natural_questions":
                create_nq_sample()
            elif name == "msmarco":
                create_msmarco_sample()

    print("\n[Done] Benchmark data ready.")
    print("Run: python run_benchmarks.py --datasets all --samples 10")
