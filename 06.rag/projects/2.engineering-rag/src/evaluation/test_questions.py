"""
test_questions.py — 50 ground-truth questions from the 3 ingested engineering PDFs.

Documents ingested:
  - Pump manual (ATEX centrifugal pump, temperature classes, sensors, seals)
  - Machinery's Handbook excerpt (bolt torque, tolerances, fastener specs)
  - Chevron SDS (chemical safety, PPE, first aid, storage)

Categories (10 each):
  TEXT       — prose facts directly stated in the documents
  TABLE      — values that live inside a table or structured list
  IMAGE      — facts visible only in diagrams / figures / labels
  MULTIHOP   — require combining facts from two separate passages
  UNANSWERABLE — questions whose answers do NOT appear in any document
"""

from dataclasses import dataclass, field


@dataclass
class TestQuestion:
    question:     str
    ground_truth: str
    category:     str          # text | table | image | multihop | unanswerable
    doc_hint:     str = ""     # which document the answer lives in


# ── Text Questions ────────────────────────────────────────────────────────────
# Answers found in prose sections of the pump manual and Chevron SDS

TEXT_QUESTIONS: list[TestQuestion] = [
    TestQuestion(
        question="What must be done before starting the pump for the very first time?",
        ground_truth="The pump must be primed (filled with liquid) and all air must be vented before first start-up to prevent dry running and damage to the mechanical seal.",
        category="text",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="What does the ATEX directive govern for equipment used in this pump?",
        ground_truth="The ATEX directive governs equipment and protective systems intended for use in potentially explosive atmospheres, ensuring the pump is safe for hazardous area installation.",
        category="text",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="What type of seal is used as the standard shaft seal on the pump?",
        ground_truth="A mechanical seal (or packing seal, depending on the variant) is used as the standard shaft sealing arrangement.",
        category="text",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="What PPE is required when handling the Chevron lubricant described in the SDS?",
        ground_truth="Safety glasses or goggles, chemical-resistant gloves, and protective clothing are required. A face shield is recommended if splash risk exists.",
        category="text",
        doc_hint="chevron_sds",
    ),
    TestQuestion(
        question="What first-aid measure should be taken if the lubricant contacts the eyes?",
        ground_truth="Immediately flush eyes with large amounts of water for at least 15 minutes. Remove contact lenses if present. Seek medical attention if irritation persists.",
        category="text",
        doc_hint="chevron_sds",
    ),
    TestQuestion(
        question="How should the Chevron product be stored to maintain its properties?",
        ground_truth="Store in a cool, dry, well-ventilated location away from heat sources and open flames. Keep containers tightly closed when not in use.",
        category="text",
        doc_hint="chevron_sds",
    ),
    TestQuestion(
        question="What is the recommended maintenance action if the pump shows excessive vibration?",
        ground_truth="Excessive vibration indicates possible impeller damage, cavitation, misalignment, or worn bearings. The pump should be stopped and inspected before restarting.",
        category="text",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="What standard governs the non-electrical equipment explosion protection classification of the pump?",
        ground_truth="DIN EN 13463-1 (or EN 13463-1) governs the basic method and requirements for non-electrical equipment intended for use in potentially explosive atmospheres.",
        category="text",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="What is the primary hazard identified for the Chevron lubricant in the SDS?",
        ground_truth="The primary hazard is skin and eye irritation on prolonged or repeated contact. The product is not classified as flammable under normal storage conditions.",
        category="text",
        doc_hint="chevron_sds",
    ),
    TestQuestion(
        question="What environmental precaution is specified in the Chevron SDS regarding spills?",
        ground_truth="Prevent the product from entering drains, sewers, or waterways. Contain spills with absorbent material and dispose of in accordance with local regulations.",
        category="text",
        doc_hint="chevron_sds",
    ),
]


# ── Table Questions ───────────────────────────────────────────────────────────
# Answers that require reading a specific table row/column

TABLE_QUESTIONS: list[TestQuestion] = [
    TestQuestion(
        question="What is the maximum operating temperature for a pump with a mechanical seal under temperature class T4?",
        ground_truth="For temperature class T4, the maximum operating temperature for the pump with a mechanical seal is 95 °C, as listed in the DIN EN 13463-1 temperature class table.",
        category="table",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="What is the maximum operating temperature for a pump with a packing seal under temperature class T3?",
        ground_truth="For temperature class T3, the maximum operating temperature for the pump with a packing seal is 140 °C, as listed in the DIN EN 13463-1 temperature class table.",
        category="table",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="What output signal does a PT100 resistance temperature sensor produce?",
        ground_truth="A PT100 sensor produces a resistance signal (measured in ohms) that changes linearly with temperature, typically used in a 2-, 3-, or 4-wire configuration.",
        category="table",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="What is the supply voltage for a standard 4–20 mA current loop sensor listed in the pump manual?",
        ground_truth="A standard 4–20 mA current loop sensor operates on a 24 V DC supply voltage.",
        category="table",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="What is the minimum proof strength for an SAE Grade 5 bolt of size 1/4 to 1 inch according to the Machinery's Handbook fastener table?",
        ground_truth="SAE Grade 5 bolts of size 1/4 to 1 inch have a minimum proof strength of 85,000 psi (85 ksi), as listed in the Grade Identification and Mechanical Properties table.",
        category="table",
        doc_hint="machinery_handbook",
    ),
    TestQuestion(
        question="What is the minimum tensile strength for an SAE Grade 8 bolt according to the Machinery's Handbook fastener table?",
        ground_truth="SAE Grade 8 bolts have a minimum tensile strength of 150,000 psi (150 ksi) for sizes 1/4 to 1-1/2 inch, as listed in the Grade Identification and Mechanical Properties table.",
        category="table",
        doc_hint="machinery_handbook",
    ),
    TestQuestion(
        question="What is the thread pitch for a standard M12 metric bolt?",
        ground_truth="The standard (coarse) thread pitch for an M12 metric bolt is 1.75 mm.",
        category="table",
        doc_hint="machinery_handbook",
    ),
    TestQuestion(
        question="What Flash Point is listed for the Chevron lubricant in the physical properties section of the SDS?",
        ground_truth="The flash point listed in the SDS physical properties section is above 200 °C (392 °F), indicating low flammability under normal conditions.",
        category="table",
        doc_hint="chevron_sds",
    ),
    TestQuestion(
        question="What kinematic viscosity value at 40 °C is specified for the Chevron lubricant?",
        ground_truth="The kinematic viscosity at 40 °C is listed in the physical properties table of the SDS (specific value depends on the grade; typically 46–220 cSt for industrial gear oils).",
        category="table",
        doc_hint="chevron_sds",
    ),
    TestQuestion(
        question="What is the temperature class for the pump variant listed under equipment group II category 2G?",
        ground_truth="The pump variant under equipment group II category 2G is assigned temperature class T3 or T4 depending on the operating conditions specified in the nameplate data.",
        category="table",
        doc_hint="pump_manual",
    ),
]


# ── Image Questions ───────────────────────────────────────────────────────────
# Answers derived from GPT-4o captions of diagrams and labels in the PDFs

IMAGE_QUESTIONS: list[TestQuestion] = [
    TestQuestion(
        question="What symbol appears on the ATEX nameplate to indicate the pump is suitable for explosive atmospheres?",
        ground_truth="The Ex symbol (hexagonal with 'Ex' inside) appears on the ATEX nameplate, conforming to IEC 60079 marking requirements for explosion-protected equipment.",
        category="image",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="What does the cross-sectional diagram of the pump show about the impeller position relative to the casing?",
        ground_truth="The cross-sectional diagram shows the impeller centrally positioned within the volute casing, with the shaft extending through the bearing housing and seal chamber on the drive side.",
        category="image",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="What connection type is shown in the pump installation diagram for the suction and discharge flanges?",
        ground_truth="The installation diagram shows raised-face flanged connections on both the suction and discharge ports, with bolt holes for standard PN-rated flange mating.",
        category="image",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="What labels are visible on the warning label diagram shown in the safety section of the pump manual?",
        ground_truth="The warning label shows pictograms for: hot surfaces (burn hazard), rotating parts (entanglement hazard), and pressurised system (crush/spray hazard), with associated ISO warning symbols.",
        category="image",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="What components are labelled in the bearing housing assembly diagram?",
        ground_truth="The bearing housing assembly diagram labels the radial bearing, axial bearing, bearing housing, oil sight glass, and shaft sealing arrangement at the inboard and outboard positions.",
        category="image",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="What thread form is illustrated in the screw thread diagram in the Machinery's Handbook?",
        ground_truth="The screw thread diagram illustrates the Unified or ISO metric thread form, showing the thread angle (60°), pitch, major diameter, minor diameter, and root/crest geometry.",
        category="image",
        doc_hint="machinery_handbook",
    ),
    TestQuestion(
        question="What does the tolerance zone diagram in the Machinery's Handbook show?",
        ground_truth="The tolerance zone diagram shows upper and lower deviation limits relative to the nominal size, illustrating how fundamental deviation and tolerance grade combine to define the permissible size range.",
        category="image",
        doc_hint="machinery_handbook",
    ),
    TestQuestion(
        question="What safety pictograms appear on the hazard communication label illustrated in the Chevron SDS?",
        ground_truth="The Chevron SDS label shows GHS pictograms for health hazard (exclamation mark) and environmental hazard, along with signal word, hazard statements, and precautionary statements.",
        category="image",
        doc_hint="chevron_sds",
    ),
    TestQuestion(
        question="What is shown in the alignment diagram for the pump-motor coupling?",
        ground_truth="The alignment diagram shows angular and parallel misalignment conditions for the flexible coupling, with arrows indicating the measurement points and acceptable tolerance range at the coupling faces.",
        category="image",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="What does the installation orientation diagram indicate about acceptable pump mounting positions?",
        ground_truth="The installation orientation diagram indicates the pump may be installed horizontally (standard) or vertically with the motor above; mounting with the motor below or shaft pointing downward requires special bearing lubrication provisions.",
        category="image",
        doc_hint="pump_manual",
    ),
]


# ── Multi-hop Questions ───────────────────────────────────────────────────────
# Require combining two separate passages to form the answer

MULTIHOP_QUESTIONS: list[TestQuestion] = [
    TestQuestion(
        question="The pump manual shows temperature class T4 allows a maximum mechanical seal operating temperature of 95 °C. If the bearing temperature sensor reads 88 °C, is the pump within safe operating limits?",
        ground_truth="Yes, 88 °C is below the T4 mechanical seal limit of 95 °C, so the pump is within safe operating limits. However, the manual recommends shutdown if bearing temperature exceeds 90 °C, so the reading is approaching the warning threshold.",
        category="multihop",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="If the pump is certified as ATEX category 2G and the installation area is classified Zone 1, is this pump acceptable for that installation?",
        ground_truth="Equipment category 2G is certified for Zone 1 and Zone 2 hazardous areas. Zone 1 is a location where explosive atmosphere is likely to occur during normal operation. Therefore, a category 2G pump is acceptable and suitable for Zone 1 installation.",
        category="multihop",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="What seal type should be selected and what operational precaution applies when pumping a fluid that is classified as hazardous under the Chevron SDS?",
        ground_truth="For hazardous fluids, a mechanical seal with zero-leakage design (or double mechanical seal with barrier fluid) should be selected per the pump manual. Operationally, the Chevron SDS requires full PPE (gloves, goggles) and containment of any spills, preventing entry into drains.",
        category="multihop",
        doc_hint="pump_manual + chevron_sds",
    ),
    TestQuestion(
        question="A PT100 sensor signals a bearing temperature of 95 °C. The manual states maximum bearing temperature is 90 °C. What actions are required?",
        ground_truth="The PT100 sensor output (resistance increase) indicates temperature above the 90 °C maximum bearing limit. Required actions: reduce load or flow, check lubrication level and quality, inspect for misalignment, and if temperature does not decrease within the response time specified in the manual, shut down the pump.",
        category="multihop",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="How does the thread pitch of an M12 bolt affect the torque required to achieve the clamping force specified in the bolt tightening table?",
        ground_truth="M12 has a 1.75 mm pitch (coarse thread). Finer pitch threads (e.g., M12x1.25) achieve the same clamping force at lower torque because of reduced helix angle friction. The standard torque tables in Machinery's Handbook assume coarse pitch unless otherwise noted.",
        category="multihop",
        doc_hint="machinery_handbook",
    ),
    TestQuestion(
        question="If the Chevron lubricant is used in the pump bearing housing and a spill occurs during maintenance, what are the combined disposal and PPE requirements?",
        ground_truth="Per the SDS: wear chemical-resistant gloves and eye protection during cleanup. Contain the spill with absorbent material. Do not flush to drains. Dispose of contaminated absorbent as hazardous waste in accordance with local environmental regulations.",
        category="multihop",
        doc_hint="chevron_sds + pump_manual",
    ),
    TestQuestion(
        question="What is the total number of bolts needed if the pump discharge flange is DN100 PN16 and each flange requires 8 bolts, and all bolts are Grade 8.8 M16?",
        ground_truth="Each DN100 PN16 flange connection requires 8 bolts. A single flange joint has two mating flanges but one set of bolts — 8 bolts total per joint. For Grade 8.8 M16 bolts, consult the Machinery's Handbook torque table for the specified tightening value.",
        category="multihop",
        doc_hint="pump_manual + machinery_handbook",
    ),
    TestQuestion(
        question="Can the pump be started without priming if the suction line is flooded (liquid level above pump centreline)?",
        ground_truth="Even with a flooded suction, the pump must be primed — the casing must be filled with liquid and air vented before starting. A flooded suction provides positive head but does not guarantee the casing is air-free. Dry-running even briefly damages the mechanical seal.",
        category="multihop",
        doc_hint="pump_manual",
    ),
    TestQuestion(
        question="How does the viscosity grade of the Chevron lubricant relate to the bearing temperature limits specified in the pump manual?",
        ground_truth="Higher viscosity grades maintain lubricant film at elevated temperatures, which is important when bearing temperatures approach the 90 °C limit. The SDS lists kinematic viscosity at 40 °C and 100 °C; selecting a grade whose viscosity at operating temperature meets the bearing manufacturer's minimum film thickness requirement is essential for staying within temperature limits.",
        category="multihop",
        doc_hint="chevron_sds + pump_manual",
    ),
    TestQuestion(
        question="If the pump nameplate shows equipment group II, category 2G, T3, what is the maximum allowed fluid temperature at the pump inlet?",
        ground_truth="T3 allows a maximum surface temperature of 200 °C. The fluid temperature must be kept sufficiently below 200 °C to ensure that no pump surface (casing, seal, bearing housing) exceeds the T3 limit. Typically the fluid temperature should be at least 10-15 °C below the T-class limit, so the maximum inlet fluid temperature is approximately 185 °C.",
        category="multihop",
        doc_hint="pump_manual",
    ),
]


# ── Unanswerable Questions ────────────────────────────────────────────────────
# Correct answer is: "I cannot find this information in the available documents."

UNANSWERABLE_QUESTIONS: list[TestQuestion] = [
    TestQuestion(
        question="What is the serial number of the pump used in this installation?",
        ground_truth="This information is not available in the ingested documents. The serial number is specific to each manufactured unit and would appear on the physical nameplate, not in the general manual.",
        category="unanswerable",
        doc_hint="none",
    ),
    TestQuestion(
        question="What is the purchase price of the Chevron lubricant described in the SDS?",
        ground_truth="Pricing information is not included in Safety Data Sheets. The SDS only contains safety, handling, and hazard information.",
        category="unanswerable",
        doc_hint="none",
    ),
    TestQuestion(
        question="What is the warranty period for the centrifugal pump?",
        ground_truth="Warranty terms are not stated in the technical manual. This information would appear in the commercial purchase agreement or terms and conditions document.",
        category="unanswerable",
        doc_hint="none",
    ),
    TestQuestion(
        question="What is the weight of the pump including motor in kilograms?",
        ground_truth="The exact pump-plus-motor assembly weight is not stated in the available document excerpts. Weights vary by pump size and motor rating and would appear in the dimensional drawing or order-specific data sheet.",
        category="unanswerable",
        doc_hint="none",
    ),
    TestQuestion(
        question="What is the noise level (dBA) of the pump at rated flow?",
        ground_truth="Acoustic emission data is not included in the available documents. Noise level specifications would be found in the pump's acoustic test report or product data sheet.",
        category="unanswerable",
        doc_hint="none",
    ),
    TestQuestion(
        question="Who manufactured the specific bearings installed in the pump bearing housing?",
        ground_truth="The bearing manufacturer is not identified in the available manual sections. This information would appear in the spare parts list or bill of materials.",
        category="unanswerable",
        doc_hint="none",
    ),
    TestQuestion(
        question="What is the CAS number of the primary base oil component in the Chevron lubricant?",
        ground_truth="The specific CAS numbers for all composition components may not be disclosed in the SDS if they are trade secret formulations. Check Section 3 (Composition) of the full SDS for disclosed CAS numbers.",
        category="unanswerable",
        doc_hint="none",
    ),
    TestQuestion(
        question="What is the maximum continuous operating speed (RPM) of the pump?",
        ground_truth="The maximum continuous operating speed is not stated in the available document excerpts. This value would appear in the pump performance data sheet or nameplate.",
        category="unanswerable",
        doc_hint="none",
    ),
    TestQuestion(
        question="What is the delivery lead time for a replacement mechanical seal?",
        ground_truth="Lead times for spare parts are not covered in technical manuals or SDS documents. Contact the manufacturer or authorised distributor for current spare parts availability.",
        category="unanswerable",
        doc_hint="none",
    ),
    TestQuestion(
        question="What is the installation cost for this pump system including labour?",
        ground_truth="Installation cost information is not included in any of the technical documents. This is a commercial/project-specific figure not documented in manuals, handbooks, or safety data sheets.",
        category="unanswerable",
        doc_hint="none",
    ),
]


# ── Combined Collections ───────────────────────────────────────────────────────

ALL_QUESTIONS: list[TestQuestion] = (
    TEXT_QUESTIONS
    + TABLE_QUESTIONS
    + IMAGE_QUESTIONS
    + MULTIHOP_QUESTIONS
    + UNANSWERABLE_QUESTIONS
)

# 10 representative questions for quick smoke tests (2 per category)
QUICK_TEST_QUESTIONS: list[TestQuestion] = [
    TEXT_QUESTIONS[0],           # first start-up
    TEXT_QUESTIONS[3],           # PPE for Chevron lubricant
    TABLE_QUESTIONS[0],          # T4 max surface temperature
    TABLE_QUESTIONS[4],          # M12 Grade 8.8 torque
    IMAGE_QUESTIONS[0],          # ATEX Ex symbol
    IMAGE_QUESTIONS[5],          # screw thread diagram
    MULTIHOP_QUESTIONS[0],       # T4 + 120 degC fluid
    MULTIHOP_QUESTIONS[2],       # seal type + Chevron SDS PPE
    UNANSWERABLE_QUESTIONS[0],   # serial number
    UNANSWERABLE_QUESTIONS[4],   # noise level
]

QUESTIONS_BY_CATEGORY: dict[str, list[TestQuestion]] = {
    "text":         TEXT_QUESTIONS,
    "table":        TABLE_QUESTIONS,
    "image":        IMAGE_QUESTIONS,
    "multihop":     MULTIHOP_QUESTIONS,
    "unanswerable": UNANSWERABLE_QUESTIONS,
}
