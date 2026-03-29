import re
from typing import List

class Guardrails:
    """安全护栏：检查敏感词、非法请求和隐私信息"""
    
    # 简单的敏感词库
    SENSITIVE_WORDS = ["非法", "暴力", "色情", "机密", "内幕"]

    @staticmethod
    def validate_input(text: str) -> bool:
        """检查输入是否合法"""
        # 1. 检查是否为空
        if not text or len(text.strip()) < 2:
            return False
        
        # 2. 检查敏感词
        for word in Guardrails.SENSITIVE_WORDS:
            if word in text:
                return False
        
        # 3. 检查是否包含过多的电话号码（保护隐私）
        phone_pattern = r'1[3-9]\d{9}'
        phones = re.findall(phone_pattern, text)
        if len(phones) > 3:
            return False
            
        return True

    @staticmethod
    def validate_plan_safety(plan_text: str) -> bool:
        """检查生成的行程是否包含不安全建议"""
        unsafe_keywords = ["危险", "禁区", "封闭"]
        for word in unsafe_keywords:
            if word in plan_text:
                return False
        return True
