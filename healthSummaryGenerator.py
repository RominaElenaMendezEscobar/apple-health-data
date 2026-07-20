import json,os
import utils
from google import genai
from dotenv import load_dotenv
from google.genai import types


class HealthSummaryGenerator:
    """
    Generates a clinical text summary from Apple Health metrics
    using Google's Gemini API.

    Reads the patient metrics from a JSON file, the clinical thresholds
    from a YAML file, and the prompt template from a text file.
    Embeds both into the prompt and runs inference via the Gemini API.

    Args:
        json_path    : Path to the patient metrics JSON file.
        yml_path     : Path to the clinical thresholds YAML file.
        prompt_path  : Path to the prompt template text file.
        model_id     : Gemini model ID (default: gemini-2.5-flash).
        max_tokens   : Maximum tokens to generate (default: 1024).
        api_key      : Google API key (from https://aistudio.google.com/apikey).
    """

    def __init__(self,
                 json_path: str,
                 yml_path: str,
                 prompt_path: str,
                 model_id: str  = "gemini-2.5-flash",
                 max_tokens: int = 4000,
                 api_key: str   = None):

        self.json_path   = json_path
        self.yml_path    = yml_path
        self.prompt_path = prompt_path
        self.model_id    = model_id
        self.max_tokens  = max_tokens
        self.api_key     = api_key

        # Populated by load()
        self.datos    = None
        self.yml      = None
        self.prompt   = None
        self.client   = None
        self.summary  = None

    def load(self) -> "HealthSummaryGenerator":
        """
        Reads all input files and initializes the Gemini client.
        Returns self for chaining.
        """
        if not self.api_key:
            raise ValueError("Falta api_key. Consigue una en https://aistudio.google.com/apikey")

        self.datos  = utils.read_json_file(self.json_path)
        self.yml    = utils.read_yml_file(self.yml_path)
        self.prompt = utils.read_txt_file(self.prompt_path)

        self.client = genai.Client(api_key=self.api_key)
        return self

    def _build_prompt(self) -> str:
        """
        Embeds the patient JSON and YAML thresholds into the prompt template.
        Replaces {datos} and {yml} placeholders with the actual content.

        Returns:
            str: The fully built prompt ready for inference.
        """
        datos_str = json.dumps(self.datos, indent=2, default=str)
        yml_str   = json.dumps(self.yml,   indent=2, default=str)

        return (self.prompt
                .replace("{datos}", datos_str)
                .replace("{yml}",   yml_str))

    def generate(self) -> str:
        """
        Runs inference against the Gemini API and returns the summary text.

        Returns:
            str: The generated clinical summary.
        """
        if self.client is None:
            raise RuntimeError("Client not loaded. Call load() first.")

        prompt = self._build_prompt()

        response = self.client.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=self.max_tokens,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        finish_reason = response.candidates[0].finish_reason if response.candidates else None
        usage = response.usage_metadata
        print(f"finish_reason: {finish_reason}")
        print(f"prompt_tokens: {usage.prompt_token_count}")
        print(f"thoughts_tokens: {getattr(usage, 'thoughts_token_count', None)}")
        print(f"output_tokens: {usage.candidates_token_count}")
        print(f"total_tokens: {usage.total_token_count}")

        self.summary = response.text
        return self.summary

    def save(self, output_path: str) -> "HealthSummaryGenerator":
        """
        Saves the generated summary to a text file.

        Args:
            output_path (str): Path where the summary will be saved.

        Returns:
            self for chaining.
        """
        if self.summary is None:
            raise RuntimeError("No summary to save. Call generate() first.")

        with open(output_path, 'w') as f:
            f.write(self.summary)
        print(f"✓ Summary saved: {output_path}")
        return self

