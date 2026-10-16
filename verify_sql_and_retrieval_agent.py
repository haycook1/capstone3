from agents.sql_agent import run_sql_agent
from agents.retrieval_agent import run_retrieval_agent

sql_result = run_sql_agent("How many active projects are there?")
retrieval_result = run_retrieval_agent("Summarize the indexed documents.")

print("SQL keys:", sorted(sql_result.keys()))
print("Retrieval keys:", sorted(retrieval_result.keys()))
print("SQL result:", sql_result)
print("Retrieval result:", retrieval_result)
