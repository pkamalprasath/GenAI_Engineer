"""
Ingest synthetic regulation documents into pgvector for RAG retrieval.
Run after seed_database.py.

python scripts/ingest_regulations.py

Creates regulation_documents table (if needed) and populates it with
synthetic ECOA, FCRA, HMDA, and Fair Housing Act excerpts + embeddings.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from configs.settings import settings

# ---------------------------------------------------------------------------
# Synthetic regulation corpus
# ---------------------------------------------------------------------------
REGULATIONS = [
    {
        "regulation_name": "ECOA",
        "full_name": "Equal Credit Opportunity Act",
        "sections": [
            {
                "section": "15 U.S.C. § 1691(a)",
                "text": (
                    "It shall be unlawful for any creditor to discriminate against any applicant, "
                    "with respect to any aspect of a credit transaction, on the basis of race, "
                    "color, religion, national origin, sex, marital status, or age (provided the "
                    "applicant has the capacity to contract); because all or part of the applicant's "
                    "income derives from any public assistance program; or because the applicant has "
                    "in good faith exercised any right under the Consumer Credit Protection Act."
                ),
            },
            {
                "section": "12 CFR § 202.6 — Rules concerning evaluation of applications",
                "text": (
                    "A creditor shall not take a prohibited basis into account in any system of "
                    "evaluating the creditworthiness of applicants. A creditor may consider age "
                    "only if: the age of an elderly applicant is used favorably; a statistically "
                    "sound, empirically derived credit system uses age; or the system is a "
                    "judgmental system that does not unfavorably consider age. Creditors must "
                    "provide applicants with adverse action notices within 30 days of a completed "
                    "application, including specific reasons for denial."
                ),
            },
            {
                "section": "12 CFR § 202.9 — Notifications",
                "text": (
                    "Within 30 days after receiving a completed application for credit, a creditor "
                    "shall notify the applicant of its action on the application. Notification of "
                    "adverse action must include a statement of the action taken, the ECOA notice, "
                    "the creditor's name and address, and a statement of specific reasons for the "
                    "action taken or disclosure of the applicant's right to a statement of reasons."
                ),
            },
        ],
    },
    {
        "regulation_name": "FCRA",
        "full_name": "Fair Credit Reporting Act",
        "sections": [
            {
                "section": "15 U.S.C. § 1681b — Permissible purposes",
                "text": (
                    "A consumer reporting agency may furnish a consumer report only in accordance "
                    "with the written instructions of the consumer to whom it relates, or to a "
                    "person which it has reason to believe intends to use the information in "
                    "connection with a credit transaction involving the consumer, employment "
                    "purposes, insurance underwriting, or a legitimate business need in connection "
                    "with a business transaction initiated by the consumer."
                ),
            },
            {
                "section": "15 U.S.C. § 1681c — Requirements relating to information in consumer reports",
                "text": (
                    "Except as authorized under subsection (b), no consumer reporting agency may "
                    "make any consumer report containing: bankruptcies older than 10 years; civil "
                    "suits, civil judgments, and records of arrest older than 7 years; paid tax "
                    "liens older than 7 years; accounts placed for collection older than 7 years; "
                    "any other adverse item of information older than 7 years. Creditors relying "
                    "on consumer reports for adverse action must provide consumers with risk-based "
                    "pricing notices and the right to obtain a free copy of their consumer report."
                ),
            },
        ],
    },
    {
        "regulation_name": "HMDA",
        "full_name": "Home Mortgage Disclosure Act",
        "sections": [
            {
                "section": "12 U.S.C. § 2803 — Maintenance of records and public disclosure",
                "text": (
                    "Each financial institution shall compile and make available to the public a "
                    "loan application register (LAR) for each calendar year. The LAR must include: "
                    "application date, loan type, loan purpose, owner-occupancy status, loan amount, "
                    "type of action taken, census tract, ethnicity of applicant and co-applicant, "
                    "race of applicant and co-applicant, sex of applicant and co-applicant, gross "
                    "annual income relied on in processing the application, and purchaser type. "
                    "Institutions must report denial reasons for rejected applications."
                ),
            },
            {
                "section": "12 CFR § 1003.4 — Compilation of reportable data",
                "text": (
                    "A financial institution shall collect data regarding applications for covered "
                    "loans that it receives, covered loans that it originates, and covered loans "
                    "that it purchases for each calendar year. For each covered loan or application, "
                    "an institution must record the data on the loan application register within "
                    "30 calendar days after the end of the calendar quarter in which final action "
                    "is taken. Data fields include DTI ratio, CLTV ratio, credit score, and "
                    "automated underwriting system results."
                ),
            },
        ],
    },
    {
        "regulation_name": "FHAct",
        "full_name": "Fair Housing Act",
        "sections": [
            {
                "section": "42 U.S.C. § 3604 — Discrimination in sale or rental of housing",
                "text": (
                    "It shall be unlawful to refuse to sell or rent after the making of a bona fide "
                    "offer, or to refuse to negotiate for the sale or rental of, or otherwise make "
                    "unavailable or deny, a dwelling to any person because of race, color, religion, "
                    "sex, familial status, or national origin. It shall also be unlawful to "
                    "discriminate against any person in the terms, conditions, or privileges of "
                    "sale or rental of a dwelling, or in the provision of services or facilities "
                    "in connection therewith, because of race, color, religion, sex, familial "
                    "status, or national origin."
                ),
            },
            {
                "section": "42 U.S.C. § 3605 — Discrimination in residential real estate transactions",
                "text": (
                    "It shall be unlawful for any person or other entity whose business includes "
                    "engaging in residential real estate-related transactions to discriminate against "
                    "any person in making available such a transaction, or in the terms or conditions "
                    "of such a transaction, because of race, color, religion, sex, handicap, "
                    "familial status, or national origin. Disparate impact claims arise where a "
                    "facially neutral policy produces a discriminatory effect without business "
                    "justification. Lenders must maintain records sufficient to demonstrate "
                    "compliance with all fair lending laws."
                ),
            },
        ],
    },
    {
        "regulation_name": "CRA",
        "full_name": "Community Reinvestment Act",
        "sections": [
            {
                "section": "12 U.S.C. § 2903 — Financial institutions; evaluation",
                "text": (
                    "In connection with its examination of a financial institution, the appropriate "
                    "Federal financial supervisory agency shall assess the institution's record of "
                    "meeting the credit needs of its entire community, including low- and "
                    "moderate-income neighborhoods, consistent with the safe and sound operation "
                    "of such institution. Performance is rated Outstanding, Satisfactory, Needs to "
                    "Improve, or Substantial Noncompliance based on lending, investment, and "
                    "service tests."
                ),
            },
        ],
    },
]


async def embed_text(text: str) -> list[float]:
    """Generate embedding via OpenAI API."""
    import os
    import openai
    api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
    client = openai.AsyncOpenAI(api_key=api_key)
    resp = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return resp.data[0].embedding


async def ensure_table(conn):
    """Create regulation_documents table with pgvector if it doesn't exist."""
    await conn.execute("""
        CREATE EXTENSION IF NOT EXISTS vector;
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS regulation_documents (
            id          SERIAL PRIMARY KEY,
            regulation_name  TEXT NOT NULL,
            full_name        TEXT NOT NULL,
            section          TEXT NOT NULL,
            content          TEXT NOT NULL,
            embedding        vector(1536),
            created_at       TIMESTAMPTZ DEFAULT now()
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS reg_docs_embedding_idx
        ON regulation_documents USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 10);
    """)
    print("  Table regulation_documents ready")


async def ingest():
    print("Regulation Ingester\n")

    conn = await asyncpg.connect(settings.database_url_sync)

    try:
        await ensure_table(conn)

        # Count existing rows
        existing = await conn.fetchval("SELECT COUNT(*) FROM regulation_documents")
        if existing > 0:
            print(f"  {existing} documents already present — skipping (use TRUNCATE to re-ingest)")
            return

        total_sections = sum(len(r["sections"]) for r in REGULATIONS)
        print(f"  Embedding {total_sections} regulation sections...\n")

        inserted = 0
        for reg in REGULATIONS:
            for sec in reg["sections"]:
                embedding = await embed_text(sec["text"])

                await conn.execute(
                    """
                    INSERT INTO regulation_documents
                        (regulation_name, full_name, section, content, embedding)
                    VALUES ($1, $2, $3, $4, $5::vector)
                    """,
                    reg["regulation_name"],
                    reg["full_name"],
                    sec["section"],
                    sec["text"],
                    str(embedding),
                )
                inserted += 1
                print(f"  [{inserted}/{total_sections}] {reg['regulation_name']} — {sec['section'][:60]}")

        print(f"\n  Inserted {inserted} regulation sections")

    finally:
        await conn.close()

    print("\nRegulation ingestion complete")
    print("   Agents can now retrieve regulations via pgvector similarity search")


if __name__ == "__main__":
    asyncio.run(ingest())
