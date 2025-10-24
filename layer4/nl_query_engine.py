"""Natural Language Query Engine for financial data queries.

This module provides natural language query capabilities including:
1. Intent recognition from user queries
2. Entity extraction (dates, amounts, accounts, companies)
3. SQL query generation from natural language
4. Query execution and result formatting
5. Query history and suggestions
"""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class NLQueryEngine:
    """Engine for processing natural language queries on financial data."""

    def __init__(self, db_path: str):
        """Initialize the NL query engine.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._query_history: List[Dict[str, Any]] = []

        # Intent keywords mapping
        self._intent_keywords = {
            "查询凭证": ["凭证", "分录", "记账凭证"],
            "查询科目": ["科目", "会计科目", "账户"],
            "查询余额": ["余额", "账面", "期末余额", "期初余额"],
            "查询明细": ["明细", "明细账", "流水"],
            "查询汇总": ["汇总", "合计", "总计", "统计"],
            "查询异常": ["异常", "错误", "问题", "风险"],
            "查询实体": ["公司", "主体", "单位", "企业"],
        }

        # Account name patterns
        self._account_patterns = {
            "现金": ["1001", "库存现金"],
            "银行存款": ["1002", "银行存款"],
            "应收账款": ["1122", "应收账款"],
            "预付账款": ["1123", "预付账款"],
            "存货": ["1405", "存货"],
            "固定资产": ["1601", "固定资产"],
            "应付账款": ["2202", "应付账款"],
            "应付职工薪酬": ["2211", "应付职工薪酬"],
            "主营业务收入": ["6001", "主营业务收入"],
            "主营业务成本": ["6401", "主营业务成本"],
            "管理费用": ["6602", "管理费用"],
            "销售费用": ["6601", "销售费用"],
            "财务费用": ["6603", "财务费用"],
        }

    def connect(self):
        """Establish database connection."""
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            logger.debug(f"Connected to database: {self.db_path}")

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    def process_query(
        self,
        query_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process a natural language query.

        Args:
            query_text: Natural language query from user
            context: Optional context (current project, entity, period, etc.)

        Returns:
            Dictionary with query results and metadata
        """
        self.connect()
        context = context or {}

        logger.info(f"Processing NL query: {query_text}")

        try:
            # Step 1: Identify intent
            intent = self._identify_intent(query_text)
            logger.info(f"Detected intent: {intent}")

            # Step 2: Extract entities
            entities = self._extract_entities(query_text, context)
            logger.info(f"Extracted entities: {entities}")

            # Step 3: Generate SQL
            sql, params = self._generate_sql(intent, entities, context)
            logger.info(f"Generated SQL: {sql}")

            # Step 4: Execute query
            results = self._execute_query(sql, params)
            logger.info(f"Query returned {len(results)} rows")

            # Step 5: Format results
            formatted_results = self._format_results(results, intent)

            # Step 6: Save to history
            self._save_to_history(query_text, intent, entities, len(results))

            return {
                "success": True,
                "query": query_text,
                "intent": intent,
                "entities": entities,
                "sql": sql,
                "row_count": len(results),
                "results": formatted_results,
                "executed_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            return {
                "success": False,
                "query": query_text,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def _identify_intent(self, query: str) -> str:
        """Identify user intent from query text.

        Args:
            query: Query text

        Returns:
            Intent category
        """
        query_lower = query.lower()

        # Check each intent category
        for intent, keywords in self._intent_keywords.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return intent

        # Default intent
        if any(word in query_lower for word in ["查", "找", "搜", "看"]):
            return "查询凭证"  # Default to voucher query

        return "通用查询"

    def _extract_entities(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract entities from query text.

        Args:
            query: Query text
            context: Context dictionary

        Returns:
            Dictionary of extracted entities
        """
        entities = {}

        # Extract dates
        entities["dates"] = self._extract_dates(query)

        # Extract amounts
        entities["amounts"] = self._extract_amounts(query)

        # Extract account names
        entities["accounts"] = self._extract_accounts(query)

        # Extract company/entity names
        entities["companies"] = self._extract_companies(query, context)

        # Extract periods
        entities["periods"] = self._extract_periods(query, context)

        # Extract comparison operators
        entities["operators"] = self._extract_operators(query)

        return entities

    def _extract_dates(self, query: str) -> List[str]:
        """Extract date expressions from query."""
        dates = []

        # YYYY-MM-DD format
        pattern1 = r'\d{4}-\d{1,2}-\d{1,2}'
        dates.extend(re.findall(pattern1, query))

        # YYYY年MM月DD日 format
        pattern2 = r'(\d{4})年(\d{1,2})月(\d{1,2})日'
        matches = re.findall(pattern2, query)
        for match in matches:
            dates.append(f"{match[0]}-{match[1].zfill(2)}-{match[2].zfill(2)}")

        # Relative dates
        if "今天" in query or "当天" in query:
            dates.append(datetime.now().strftime("%Y-%m-%d"))
        elif "昨天" in query:
            from datetime import timedelta
            dates.append((datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"))

        return dates

    def _extract_amounts(self, query: str) -> List[Dict[str, Any]]:
        """Extract amount expressions from query."""
        amounts = []

        # Pattern: 数字 + 万/千/百/十/元
        patterns = [
            (r'(\d+\.?\d*)万', lambda x: float(x) * 10000),
            (r'(\d+\.?\d*)千', lambda x: float(x) * 1000),
            (r'(\d+\.?\d*)百', lambda x: float(x) * 100),
            (r'(\d+\.?\d*)十', lambda x: float(x) * 10),
            (r'(\d+\.?\d*)元', lambda x: float(x)),
        ]

        for pattern, converter in patterns:
            matches = re.findall(pattern, query)
            for match in matches:
                amounts.append({
                    "value": converter(match),
                    "original": match
                })

        return amounts

    def _extract_accounts(self, query: str) -> List[Dict[str, Any]]:
        """Extract account references from query."""
        accounts = []

        for account_name, patterns in self._account_patterns.items():
            for pattern in patterns:
                if pattern in query:
                    accounts.append({
                        "name": account_name,
                        "code": patterns[0] if patterns[0].isdigit() else None
                    })
                    break

        # Also check for account code patterns (4-digit codes)
        code_pattern = r'\b(\d{4})\b'
        codes = re.findall(code_pattern, query)
        for code in codes:
            if code not in [a.get("code") for a in accounts]:
                accounts.append({
                    "code": code,
                    "name": None
                })

        return accounts

    def _extract_companies(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> List[str]:
        """Extract company/entity references from query."""
        companies = []

        # Use context to find entity names
        current_project = context.get("current_project")
        if current_project:
            # Would query entities table here
            pass

        # Extract common company name patterns
        # This is simplified - would need NER for production
        if "母公司" in query:
            companies.append("母公司")
        if "子公司" in query:
            companies.append("子公司")

        return companies

    def _extract_periods(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> List[str]:
        """Extract fiscal period references from query."""
        periods = []

        # YYYY-MM format
        pattern1 = r'(\d{4})-(\d{1,2})'
        matches = re.findall(pattern1, query)
        for match in matches:
            periods.append(f"{match[0]}-{match[1].zfill(2)}")

        # YYYY年MM月 format
        pattern2 = r'(\d{4})年(\d{1,2})月'
        matches = re.findall(pattern2, query)
        for match in matches:
            periods.append(f"{match[0]}-{match[1].zfill(2)}")

        # Year only
        pattern3 = r'(\d{4})年'
        matches = re.findall(pattern3, query)
        for match in matches:
            if match not in [p.split("-")[0] for p in periods]:
                periods.append(match)

        # Use context default period if none found
        if not periods and context.get("current_period"):
            periods.append(context["current_period"])

        return periods

    def _extract_operators(self, query: str) -> Dict[str, Any]:
        """Extract comparison operators from query."""
        operators = {
            "comparison": None,
            "aggregation": None,
            "sorting": None
        }

        # Comparison operators
        if any(word in query for word in ["大于", "超过", "多于", ">"]):
            operators["comparison"] = ">"
        elif any(word in query for word in ["小于", "少于", "低于", "<"]):
            operators["comparison"] = "<"
        elif any(word in query for word in ["等于", "是", "="]):
            operators["comparison"] = "="

        # Aggregation
        if any(word in query for word in ["合计", "总计", "汇总", "求和"]):
            operators["aggregation"] = "SUM"
        elif any(word in query for word in ["平均", "平均值"]):
            operators["aggregation"] = "AVG"
        elif any(word in query for word in ["最大", "最高"]):
            operators["aggregation"] = "MAX"
        elif any(word in query for word in ["最小", "最低"]):
            operators["aggregation"] = "MIN"
        elif any(word in query for word in ["计数", "数量", "个数"]):
            operators["aggregation"] = "COUNT"

        # Sorting
        if any(word in query for word in ["降序", "从大到小", "从高到低"]):
            operators["sorting"] = "DESC"
        elif any(word in query for word in ["升序", "从小到大", "从低到高"]):
            operators["sorting"] = "ASC"

        return operators

    def _generate_sql(
        self,
        intent: str,
        entities: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[str, List[Any]]:
        """Generate SQL query from intent and entities.

        Args:
            intent: Query intent
            entities: Extracted entities
            context: Context dictionary

        Returns:
            Tuple of (SQL query, parameters)
        """
        if intent == "查询凭证":
            return self._generate_voucher_query(entities, context)
        elif intent == "查询科目":
            return self._generate_account_query(entities, context)
        elif intent == "查询余额":
            return self._generate_balance_query(entities, context)
        elif intent == "查询明细":
            return self._generate_detail_query(entities, context)
        elif intent == "查询汇总":
            return self._generate_summary_query(entities, context)
        else:
            return self._generate_general_query(entities, context)

    def _generate_voucher_query(
        self,
        entities: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[str, List[Any]]:
        """Generate SQL for voucher query."""
        sql = """
            SELECT v.voucher_number, v.voucher_date, v.summary,
                   vd.account_code, vd.account_name,
                   vd.debit_amount, vd.credit_amount
            FROM vouchers v
            LEFT JOIN voucher_details vd ON v.voucher_id = vd.voucher_id
            WHERE 1=1
        """
        params = []

        # Add date filter
        if entities.get("dates"):
            sql += " AND v.voucher_date >= ?"
            params.append(entities["dates"][0])

        # Add period filter
        if entities.get("periods"):
            sql += " AND v.fiscal_period = ?"
            params.append(entities["periods"][0])

        # Add account filter
        if entities.get("accounts"):
            account_codes = [a["code"] for a in entities["accounts"] if a.get("code")]
            if account_codes:
                placeholders = ",".join(["?"] * len(account_codes))
                sql += f" AND vd.account_code IN ({placeholders})"
                params.extend(account_codes)

        # Add amount filter
        if entities.get("amounts") and entities.get("operators", {}).get("comparison"):
            operator = entities["operators"]["comparison"]
            amount = entities["amounts"][0]["value"]
            sql += f" AND (vd.debit_amount {operator} ? OR vd.credit_amount {operator} ?)"
            params.extend([amount, amount])

        # Add sorting
        sorting = entities.get("operators", {}).get("sorting", "DESC")
        sql += f" ORDER BY v.voucher_date {sorting}, v.voucher_number"

        # Add limit
        sql += " LIMIT 1000"

        return sql, params

    def _generate_account_query(
        self,
        entities: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[str, List[Any]]:
        """Generate SQL for account query."""
        sql = """
            SELECT DISTINCT account_code, account_name
            FROM voucher_details
            WHERE 1=1
        """
        params = []

        # Add account filter
        if entities.get("accounts"):
            conditions = []
            for account in entities["accounts"]:
                if account.get("code"):
                    conditions.append("account_code = ?")
                    params.append(account["code"])
                if account.get("name"):
                    conditions.append("account_name LIKE ?")
                    params.append(f"%{account['name']}%")

            if conditions:
                sql += " AND (" + " OR ".join(conditions) + ")"

        sql += " ORDER BY account_code"

        return sql, params

    def _generate_balance_query(
        self,
        entities: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[str, List[Any]]:
        """Generate SQL for balance query."""
        sql = """
            SELECT account_code, account_name,
                   SUM(debit_amount) as total_debit,
                   SUM(credit_amount) as total_credit,
                   SUM(debit_amount) - SUM(credit_amount) as balance
            FROM voucher_details vd
            LEFT JOIN vouchers v ON vd.voucher_id = v.voucher_id
            WHERE 1=1
        """
        params = []

        # Add period filter
        if entities.get("periods"):
            sql += " AND v.fiscal_period = ?"
            params.append(entities["periods"][0])

        # Add account filter
        if entities.get("accounts"):
            account_codes = [a["code"] for a in entities["accounts"] if a.get("code")]
            if account_codes:
                placeholders = ",".join(["?"] * len(account_codes))
                sql += f" AND vd.account_code IN ({placeholders})"
                params.extend(account_codes)

        sql += " GROUP BY account_code, account_name"
        sql += " ORDER BY account_code"

        return sql, params

    def _generate_detail_query(
        self,
        entities: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[str, List[Any]]:
        """Generate SQL for detail ledger query."""
        return self._generate_voucher_query(entities, context)

    def _generate_summary_query(
        self,
        entities: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[str, List[Any]]:
        """Generate SQL for summary query."""
        agg_func = entities.get("operators", {}).get("aggregation", "SUM")

        sql = f"""
            SELECT account_code, account_name,
                   {agg_func}(debit_amount) as total_debit,
                   {agg_func}(credit_amount) as total_credit
            FROM voucher_details vd
            LEFT JOIN vouchers v ON vd.voucher_id = v.voucher_id
            WHERE 1=1
        """
        params = []

        # Add period filter
        if entities.get("periods"):
            sql += " AND v.fiscal_period = ?"
            params.append(entities["periods"][0])

        sql += " GROUP BY account_code, account_name"
        sql += " ORDER BY account_code"

        return sql, params

    def _generate_general_query(
        self,
        entities: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[str, List[Any]]:
        """Generate general purpose query."""
        return self._generate_voucher_query(entities, context)

    def _execute_query(self, sql: str, params: List[Any]) -> pd.DataFrame:
        """Execute SQL query and return results.

        Args:
            sql: SQL query string
            params: Query parameters

        Returns:
            DataFrame with query results
        """
        try:
            df = pd.read_sql_query(sql, self.conn, params=params)
            return df
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def _format_results(
        self,
        results: pd.DataFrame,
        intent: str
    ) -> List[Dict[str, Any]]:
        """Format query results for display.

        Args:
            results: Query results DataFrame
            intent: Query intent

        Returns:
            List of result dictionaries
        """
        if results.empty:
            return []

        # Convert to list of dicts
        formatted = results.to_dict('records')

        # Add formatting based on intent
        for row in formatted:
            # Format amounts
            for key in row.keys():
                if 'amount' in key.lower() or key in ['balance', 'total_debit', 'total_credit']:
                    if row[key] is not None:
                        row[key] = round(float(row[key]), 2)

        return formatted

    def _save_to_history(
        self,
        query: str,
        intent: str,
        entities: Dict[str, Any],
        result_count: int
    ):
        """Save query to history."""
        self._query_history.append({
            "query": query,
            "intent": intent,
            "entities": entities,
            "result_count": result_count,
            "timestamp": datetime.now().isoformat()
        })

        # Keep only last 100 queries
        if len(self._query_history) > 100:
            self._query_history = self._query_history[-100:]

    def get_query_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent query history.

        Args:
            limit: Maximum number of queries to return

        Returns:
            List of recent queries
        """
        return self._query_history[-limit:]

    def get_query_suggestions(self, partial_query: str) -> List[str]:
        """Get query suggestions based on partial input.

        Args:
            partial_query: Partial query text

        Returns:
            List of suggested queries
        """
        suggestions = [
            "查询2024年12月的全部凭证",
            "查询主营业务收入科目余额",
            "查询超过10万元的凭证",
            "查询管理费用明细",
            "查询现金和银行存款余额",
            "查询应收账款汇总",
            "查询固定资产明细账",
            "查询2024年利润表数据"
        ]

        # Filter by partial query
        if partial_query:
            partial_lower = partial_query.lower()
            suggestions = [s for s in suggestions if partial_lower in s.lower()]

        return suggestions[:5]


if __name__ == "__main__":
    # Test NL query engine
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/dap.db"

    print(f"\n{'='*60}")
    print(f"Natural Language Query Engine Test")
    print(f"{'='*60}\n")

    with NLQueryEngine(db_path) as engine:
        # Test queries
        test_queries = [
            "查询2024年12月的凭证",
            "查询主营业务收入科目",
            "查询超过10万元的凭证",
            "查询管理费用明细"
        ]

        for query in test_queries:
            print(f"\n查询: {query}")
            result = engine.process_query(query, {"current_period": "2024-12"})
            print(f"意图: {result.get('intent')}")
            print(f"实体: {result.get('entities')}")
            print(f"结果数: {result.get('row_count', 0)}")
