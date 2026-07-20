from healthChartBuilder import HealthChartBuilder
from healthDataReader import HealthDataReader
from healthReportPDF import HealthReportPDF
from healthSummaryGenerator import HealthSummaryGenerator
import utils
import os


if __name__ == "__main__":

    patients = [
        ("patients/alex_28m.xml",   "Alex Torres"),
        ("patients/maria_61f.xml",  "María González"),
        ("patients/carlos_68m.xml", "Carlos Mendez"),
    ]

    os.makedirs("reports", exist_ok=True)
    os.makedirs("charts",  exist_ok=True)
    os.makedirs("data",    exist_ok=True)

    env = utils.read_env()  # una sola vez, no hace falta releer el .env por paciente

    for xml_path, name in patients:
        print(f"\n── {name} ──")
        prefix = name.lower().replace(' ', '_')

        # Step 1: read and compute
        reader = HealthDataReader(xml_path).load()

        # Step 1b: save the compact LLM-friendly summary for this patient
        reader.save(write_llm_summary=True, file_name=prefix)

        # Step 2: generate charts
        builder = HealthChartBuilder(
            metrics    = reader.metrics,
            output_dir = "charts",
            prefix     = prefix,
        )
        charts = builder.build_all()

        # Step 2b: generate the narrative summary with Gemini
        generator = HealthSummaryGenerator(
            json_path   = f"data/{prefix}_llm_summary.json",
            yml_path    = "config/params_health.yml",
            prompt_path = "prompt/prompt_summary.txt",
            api_key     = env["gemini_api_key"],
        ).load()
        llm_text = generator.generate()

        # Step 3: build PDF
        HealthReportPDF(
            metrics        = reader.metrics,
            charts         = charts,
            patient_name   = name,
            date_of_birth  = reader.date_of_birth,
            biological_sex = reader.biological_sex,
            start_date     = reader.df['start'].min(),
            end_date       = reader.df['start'].max(),
            out_path       = f"reports/{prefix}_report.pdf",
            llm_summary    = llm_text,
        ).build()