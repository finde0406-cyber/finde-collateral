"""
DART API 연동 (준비)
"""
from config import DART_API_KEY

class DARTConnector:
    def __init__(self, api_key=None):
        self.api_key = api_key or DART_API_KEY
        self.base_url = "https://opendart.fss.or.kr/api"
    
    def is_connected(self):
        return self.api_key is not None
    
    # API 발급 후 구현
    def get_financial_statement(self, stock_code):
        pass
    
    def get_audit_opinion(self, stock_code):
        pass