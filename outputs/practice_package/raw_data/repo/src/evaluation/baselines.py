from __future__ import annotations

    from typing import Any, Dict, List


    def lexical_schema_linking(question: str, tables_json: Dict[str, Any]) -> Dict[str, Any]:
        question_tokens = {tok.lower() for tok in question.replace('_', ' ').split() if tok.strip()}
        table_names = tables_json.get('table_names_original') or tables_json.get('table_names') or []
        column_names = tables_json.get('column_names_original') or tables_json.get('column_names') or []
        matched_tables = set()
        matched_columns: List[tuple[int, str]] = []
        for idx, table in enumerate(table_names):
            table_tokens = {tok.lower() for tok in str(table).replace('_', ' ').split()}
            if question_tokens & table_tokens:
                matched_tables.add(idx)
        for table_idx, column in column_names:
            if table_idx < 0:
                continue
            column_tokens = {tok.lower() for tok in str(column).replace('_', ' ').split()}
            if question_tokens & column_tokens:
                matched_tables.add(table_idx)
                matched_columns.append((table_idx, column))
        if not matched_tables:
            matched_tables = set(range(len(table_names)))
            matched_columns = [(i, col) for i, col in column_names if i >= 0]
        return {'db_id': tables_json.get('db_id'), 'table_indexes': sorted(matched_tables), 'columns': matched_columns}


    def build_b1_prompt(question: str, reduced_schema_context: str) -> str:
        return 'You are a text-to-SQL assistant. Generate one SQLite SQL query.
Use only the reduced schema. Return SQL only.

' + reduced_schema_context + '

Question: ' + question + '
SQL:'


    def compare_b0_b1_result_record(b0_record: Dict[str, Any], b1_record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'idx': b0_record.get('idx', b1_record.get('idx')),
            'db_id': b0_record.get('db_id', b1_record.get('db_id')),
            'question': b0_record.get('question', b1_record.get('question')),
            'b0_executable': b0_record.get('executable'),
            'b0_execution_match': b0_record.get('execution_match'),
            'b1_executable': b1_record.get('executable'),
            'b1_execution_match': b1_record.get('execution_match'),
            'changed': b0_record.get('generated_sql') != b1_record.get('generated_sql'),
            'b0_error_type': b0_record.get('error_type'),
            'b1_error_type': b1_record.get('error_type'),
        }
