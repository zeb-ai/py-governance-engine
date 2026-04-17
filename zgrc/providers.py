class Providers:
    BEDROCK = "bedrock"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    AZURE = "azure"
    GEMINI = "gemini"


PACKAGE_MAP = {
    "boto3": Providers.BEDROCK,
    "anthropic": Providers.ANTHROPIC,
    "openai": Providers.OPENAI,
    "azure-ai-inference": Providers.AZURE,
    "google-generativeai": Providers.GEMINI,
}
