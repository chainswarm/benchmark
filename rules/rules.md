NEVER write tests
NEVER provide fallback code
NEVER use emoticons in logs
NEVER create data migrations
NEVER create mocks
NEVER return None or default values, if something went wrong raise exception
NEVER put reasoning or decision thoughts in methods code comments or method / class documentation, we desing clear system 
NEVER put method or class documentation strings / comments, class and method names are self descriptive, for example
    def get_exchange_labels_for_addresses(self, network: str, addresses: List[str]) -> Dict:
        """Get exchange labels for addresses.""" DOES NOT NEEDS THIS COMMENT !!
class RiskScoringTask(BaseDataPipelineTask):
    """Simplified risk scoring task using string-based operations."""  NO comments like this at all, NO COMMENTS they create noize !!! and class name says the same !!

ALWAYS assume we write new system
ALWAYS assume that the user will test the code by himself
ALWAYS fail fast, raise ValueErrors, log errors in highest entrypoint, use logging decorators @log_error, we use loguru for logging
ALWAYS put pure documentation comments without any decision reasoning


WE USE bash, we dont use powershell