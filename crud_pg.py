import psycopg2
import asyncpg
import os
from typing import Optional, List

from dataclasses import dataclass
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

from dotenv import load_dotenv

load_dotenv()

DB_DSN = os.getenv("DB_DSN")

def create_notes_table():
    """
    Establishes a 'notes' table if it doesn't exist, with 'id', 'title', and 'text'.
    """
    create_table_query = """
    CREATE TABLE IF NOT EXISTS notes (
        id SERIAL PRIMARY KEY,
        title VARCHAR(200) UNIQUE NOT NULL,
        text TEXT NOT NULL
    );
    """
    try:
        connection = psycopg2.connect(DB_DSN)
        cursor = connection.cursor()
        cursor.execute(create_table_query)
        connection.commit()
        print("Successfully created or verified the 'notes' table.")
    except psycopg2.Error as e:
        print(f"Error while creating table: {e}")
    finally:
        if connection:
            cursor.close()
            connection.close()
def check_table_exists(table_name: str) -> bool:
    """
    Checks whether a specified table is present in the DB.
    """
    query = """
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name = %s
    );
    """
    try:
        connection = psycopg2.connect(DB_DSN)
        cursor = connection.cursor()
        cursor.execute(query, (table_name,))
        exists = cursor.fetchone()[0]
        return exists
    except psycopg2.Error as e:
        print(f"Error checking table: {e}")
        return False
    finally:
        if connection:
            cursor.close()
            connection.close()

class DatabaseConn:
    def __init__(self):
        """
        Store the DSN (Data Source Name) for connecting.
        """
        self.dsn = DB_DSN
    async def _connect(self):
        """
        Opens an async connection to PostgreSQL.
        """
        return await asyncpg.connect(self.dsn)
    async def add_note(self, title: str, text: str) -> bool:
        """
        Inserts a note with the given title and text.
        If a note with the same title exists, it won't overwrite.
        """
        query = """
        INSERT INTO notes (title, text)
        VALUES ($1, $2)
        ON CONFLICT (title) DO NOTHING;
        """
        conn = await self._connect()
        try:
            result = await conn.execute(query, title, text)
            return result == "INSERT 0 1"
        finally:
            await conn.close()
    async def get_note_by_title(self, title: str) -> Optional[dict]:
        """
        Retrieves the note matching the specified title. Returns a dict or None.
        """
        query = "SELECT title, text FROM notes WHERE title = $1;"
        conn = await self._connect()
        try:
            record = await conn.fetchrow(query, title)
            if record:
                return {"title": record["title"], "text": record["text"]}
            return None
        finally:
            await conn.close()
    async def list_all_titles(self) -> List[str]:
        """
        Fetches and returns all note titles.
        """
        query = "SELECT title FROM notes ORDER BY title;"
        conn = await self._connect()
        try:
            results = await conn.fetch(query)
            return [row["title"] for row in results]
        finally:
            await conn.close()

@dataclass
class NoteIntent:
    action: str
    title: Optional[str] = None
    text: Optional[str] = None
@dataclass
class NoteDependencies:
    db: DatabaseConn
class NoteResponse(BaseModel):
    message: str
    note: Optional[dict] = None
    titles: Optional[List[str]] = None
# 1. Agent for parsing the user's intent
intent_model = OpenAIModel('gpt-4o-mini')
intent_agent = Agent(
    intent_model,
    result_type=NoteIntent,
    system_prompt=(
        "You are an intent extraction assistant. Understand what the user wants "
        "(e.g., create, retrieve, list) and extract the relevant data like title and text. "
        "Your output format must be a JSON-like structure with keys: action, title, text."
    )
)
# 2. Agent for executing the identified action
action_model = OpenAIModel('gpt-4o')
action_agent = Agent(
    action_model,
    deps_type=NoteDependencies,
    result_type=NoteResponse,
    system_prompt=(
        "You are an action executor for a note management system. Your job is to perform the requested action based on the user's intent. "
        "There are three actions: 'create' (to add a new note), 'retrieve' (to get an existing note), and 'list' (to show all note titles). "
        "For a 'retrieve' action, first check the db and capture the best matched title for user's intent and based on the title, and retrieve."
    )
)

# Tools for action_agent
@action_agent.tool
async def create_note_tool(ctx: RunContext[NoteDependencies], title: str, text: str) -> NoteResponse:
    db = ctx.deps.db
    success = await db.add_note(title, text)
    return NoteResponse(message="CREATED:SUCCESS" if success else "CREATED:FAILED")
@action_agent.tool
async def retrieve_note_tool(ctx: RunContext[NoteDependencies], title: str) -> NoteResponse:
    db = ctx.deps.db
    note = await db.get_note_by_title(title)
    return NoteResponse(message="GET:SUCCESS", note=note) if note else NoteResponse(message="GET:FAILED")
@action_agent.tool
async def list_notes_tool(ctx: RunContext[NoteDependencies]) -> NoteResponse:
    db = ctx.deps.db
    all_titles = await db.list_all_titles()
    return NoteResponse(message="LIST:SUCCESS", titles=all_titles)
async def handle_user_query(user_input: str, deps: NoteDependencies) -> NoteResponse:
    # Determine user intent
    intent = await intent_agent.run(user_input)
    print(intent.data)
    if intent.data.action == "create":
        query = f"Create a note named '{intent.data.title}' with the text '{intent.data.text}'."
        response = await action_agent.run(query, deps=deps)
        return response.data
    elif intent.data.action == "retrieve":
        query = f"Retrieve the note titled '{intent.data.title}'."
        response = await action_agent.run(query, deps=deps)
        return response.data
    elif intent.data.action == "list":
        query = "List the titles of all notes."
        response = await action_agent.run(query, deps=deps)
        return response.data
    else:
        return NoteResponse(message="Action not recognized.")
async def ask(query: str):
    db_conn = DatabaseConn()
    note_deps = NoteDependencies(db=db_conn)
    return await handle_user_query(query, note_deps)