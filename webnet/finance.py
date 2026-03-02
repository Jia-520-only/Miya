"""
财务子网
处理财务相关事务
"""
from typing import Dict, List
from datetime import datetime


class FinanceNet:
    """财务子网"""

    def __init__(self):
        self.net_id = 'finance_net'
        self.capabilities = [
            'expense_tracking',
            'budget_management',
            'financial_advice'
        ]

        # 财务数据
        self.transactions = []
        self.budgets = {}
        self.accounts = {}

    def add_transaction(self, amount: float, category: str,
                       description: str = '', timestamp: str = None) -> bool:
        """添加交易"""
        if not timestamp:
            timestamp = datetime.now().isoformat()

        transaction = {
            'id': len(self.transactions),
            'amount': amount,
            'category': category,
            'description': description,
            'timestamp': timestamp
        }

        self.transactions.append(transaction)
        return True

    def get_transactions(self, category: str = None, limit: int = 20) -> List[Dict]:
        """获取交易记录"""
        transactions = self.transactions

        if category:
            transactions = [t for t in transactions if t.get('category') == category]

        # 返回最近的交易
        return transactions[-limit:] if transactions else []

    def set_budget(self, category: str, amount: float) -> None:
        """设置预算"""
        self.budgets[category] = amount

    def get_budget(self, category: str) -> float:
        """获取预算"""
        return self.budgets.get(category, 0.0)

    def check_budget_status(self, category: str = None) -> Dict:
        """检查预算状态"""
        result = {}

        if category:
            # 检查单个类别
            budget = self.budgets.get(category, 0)
            spent = self._calculate_spent(category)
            remaining = budget - spent
            percentage = (spent / budget * 100) if budget > 0 else 0

            result[category] = {
                'budget': budget,
                'spent': round(spent, 2),
                'remaining': round(remaining, 2),
                'percentage': round(percentage, 2)
            }
        else:
            # 检查所有类别
            for cat, budget in self.budgets.items():
                spent = self._calculate_spent(cat)
                remaining = budget - spent
                percentage = (spent / budget * 100) if budget > 0 else 0

                result[cat] = {
                    'budget': budget,
                    'spent': round(spent, 2),
                    'remaining': round(remaining, 2),
                    'percentage': round(percentage, 2)
                }

        return result

    def _calculate_spent(self, category: str) -> float:
        """计算已花费金额"""
        return sum(
            abs(t['amount'])
            for t in self.transactions
            if t['amount'] < 0 and t.get('category') == category
        )

    def get_summary(self) -> Dict:
        """获取财务摘要"""
        income = sum(t['amount'] for t in self.transactions if t['amount'] > 0)
        expense = sum(abs(t['amount']) for t in self.transactions if t['amount'] < 0)
        balance = income - expense

        return {
            'total_income': round(income, 2),
            'total_expense': round(expense, 2),
            'balance': round(balance, 2),
            'transaction_count': len(self.transactions)
        }

    def process_request(self, request: Dict) -> Dict:
        """处理财务请求"""
        req_type = request.get('type')

        if req_type == 'add_transaction':
            success = self.add_transaction(
                request.get('amount'),
                request.get('category'),
                request.get('description'),
                request.get('timestamp')
            )
            return {'success': success}
        elif req_type == 'get_transactions':
            transactions = self.get_transactions(request.get('category'))
            return {'transactions': transactions}
        elif req_type == 'get_summary':
            summary = self.get_summary()
            return summary
        elif req_type == 'check_budget':
            status = self.check_budget_status(request.get('category'))
            return status
        else:
            return {'error': 'Unknown request type'}
