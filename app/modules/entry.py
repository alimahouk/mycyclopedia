import concurrent.futures
from datetime import datetime
import json
import sched
import threading
import time
from typing import (
    Any,
    Iterator,
    Type,
    TypeVar
)
import uuid

import markdown
from serpapi import GoogleSearch

from app.config import (
    ChatMessageSenderRole,
    Configuration,
    DatabaseTable,
    ProtocolKey,
    ResponseStatus,
    UserTopicProficiency
)
from app.llm import gpt
from app.modules import util
from app.modules.analytics import AnalyticsTopicHistory
from app.modules.chat_message import ChatMessage
from app.modules.db import RelationalDB
from app.modules.user import User
from app.modules.user_session import UserSession


###########
# CLASSES #
###########


T = TypeVar("T", bound="Entry")
X = TypeVar("X", bound="EntryCoverImage")
U = TypeVar("U", bound="EntryFunFact")
Y = TypeVar("Y", bound="EntryRelatedTopic")
V = TypeVar("V", bound="EntrySection")
W = TypeVar("W", bound="EntryStat")


class EntryPurgeJob(threading.Thread):
    """
    Periodically delete stale entries from unregistered users.
    """

    def __init__(self) -> None:
        super().__init__(daemon=True)

    def purge(self,
              scheduled_task) -> None:
        Entry.purge()
        scheduled_task.enter(
            Configuration.ENTRY_PURGE_CHECK_INTERVAL,
            1,
            self.purge,
            (scheduled_task,)
        )

    def run(self) -> None:
        entry_purge_scheduled_task = sched.scheduler(time.time, time.sleep)
        entry_purge_scheduled_task.enter(
            Configuration.ENTRY_PURGE_CHECK_INTERVAL,
            1,
            self.purge,
            (entry_purge_scheduled_task,)
        )
        entry_purge_scheduled_task.run()


class Entry:
    def __init__(self,
                 data: dict = {}) -> None:
        self.cover_image: EntryCoverImage = None
        self.creation_timestamp: datetime = None
        self.fun_facts: list[EntryFunFact] = []
        self.id: uuid.UUID = None
        self.permalink: str = None
        self.proficiency: UserTopicProficiency = None
        self.related_topics: list[EntryRelatedTopic] = []
        self.sections: list[EntrySection] = []
        self.stats: list[EntryStat] = []
        self.summary: str = None
        self.topic: str = None
        self.user: User = None
        self.user_id: int = None

        if data:
            if ProtocolKey.CREATION_TIMESTAMP in data:
                self.email_address: datetime = data[ProtocolKey.CREATION_TIMESTAMP]

            if ProtocolKey.ID in data:
                self.id: uuid.UUID = data[ProtocolKey.ID]

            if ProtocolKey.PROFICIENCY in data:
                self.proficiency = UserTopicProficiency(data[ProtocolKey.PROFICIENCY])

            if ProtocolKey.SUMMARY in data:
                self.summary: str = data[ProtocolKey.SUMMARY]

            if ProtocolKey.TOPIC in data:
                self.topic: str = data[ProtocolKey.TOPIC]

            if ProtocolKey.USER in data:
                self.user: User = User(data[ProtocolKey.USER])

            if ProtocolKey.USER_ID in data:
                self.user_id: int = data[ProtocolKey.USER_ID]

        if self.id:
            self.permalink = f"{Configuration.BASE_URL}/e/{str(self.id)}"

            self.cover_image = EntryCoverImage.get_for_entry(self.id)
            self.fun_facts = EntryFunFact.get_all_for_entry(self.id)
            self.related_topics = EntryRelatedTopic.get_all_for_entry(self.id)
            self.sections = EntrySection.get_all_for_entry(self.id)
            self.stats = EntryStat.get_all_for_entry(self.id)

        if self.user_id and not self.user:
            self.user = User.get_by_id(self.user_id)

    def __eq__(self,
               __o: object) -> bool:
        ret = False
        if isinstance(__o, type(self)) and \
                self.id == __o.id:
            ret = True
        return ret

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        ret = ""
        if self.id:
            ret += f"Entry {self.id} ('{self.topic}')"
        return ret

    def as_dict(self) -> dict[str, Any]:
        serialized = {
            ProtocolKey.ID: str(self.id),
            ProtocolKey.PERMALINK: self.permalink,
            ProtocolKey.PROFICIENCY: self.proficiency,
            ProtocolKey.TOPIC: self.topic
        }

        if self.cover_image:
            serialized[ProtocolKey.COVER_IMAGE] = self.cover_image.as_dict()

        if self.creation_timestamp:
            serialized[ProtocolKey.CREATION_DATE] = self.creation_timestamp.strftime("%e %b %Y")
            serialized[ProtocolKey.CREATION_TIMESTAMP] = self.creation_timestamp.astimezone().isoformat()

        if self.fun_facts:
            facts_serialized = []
            for fact in self.fun_facts:
                facts_serialized.append(fact.as_dict())
            serialized[ProtocolKey.FUN_FACTS] = facts_serialized

        if self.related_topics:
            related_topics_serialized = []
            for topic in self.related_topics:
                related_topics_serialized.append(topic.as_dict())
            serialized[ProtocolKey.RELATED_TOPICS] = related_topics_serialized

        if self.sections:
            sections_serialized = []
            for section in self.sections:
                sections_serialized.append(section.as_dict())
            serialized[ProtocolKey.SECTIONS] = sections_serialized

        if self.stats:
            stats_serialized = []
            for stat in self.stats:
                stats_serialized.append(stat.as_dict())
            serialized[ProtocolKey.STATS] = stats_serialized

        if self.summary:
            serialized[ProtocolKey.SUMMARY] = self.summary

        if self.user:
            serialized[ProtocolKey.USER] = self.user.as_dict()

        if self.user_id:
            serialized[ProtocolKey.USER_ID] = self.user_id

        return serialized

    @classmethod
    def create(cls: Type,
               proficiency: UserTopicProficiency = None,
               summary: str = None,
               topic: str = None,
               user_id: int = None) -> T:
        """
        Call this method to create an Entry object.
        """

        if not isinstance(proficiency, UserTopicProficiency):
            raise TypeError(f"Argument 'proficiency' must be of type UserTopicProficiency, not {type(proficiency)}.")

        if not isinstance(topic, str):
            raise TypeError(f"Argument 'topic' must be of type str, not {type(topic)}.")

        if user_id:
            if not isinstance(user_id, int):
                raise TypeError(f"Argument 'user_id' must be of type int, not {type(user_id)}.")

            if user_id <= 0:
                raise ValueError("Argument 'user_id' must be a positive, non-zero integer.")

        ret: Type = None
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                INSERT INTO
                    {DatabaseTable.ENTRY}
                    ({ProtocolKey.PROFICIENCY}, {ProtocolKey.SUMMARY}, {ProtocolKey.TOPIC},
                     {ProtocolKey.USER_ID})
                VALUES
                    (%s, %s, %s,
                     %s)
                RETURNING *;
                """,
                (proficiency, summary, topic,
                 user_id)
            )
            result = cursor.fetchone()
            db.connection.commit()
            if result:
                ret = cls(result)
        except Exception as e:
            print(e)
        finally:
            db.close()

        return ret

    def delete(self) -> None:
        if not self.id:
            raise Exception("Entry deletion requires an entry ID.")

        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                DELETE FROM
                    {DatabaseTable.ENTRY}
                WHERE
                    {ProtocolKey.ID} = %s;
                """,
                (self.id,)
            )
            db.connection.commit()
        except Exception as e:
            print(e)
        finally:
            db.close()

    @classmethod
    def get_all_by_user(cls: Type,
                        user_id: int,
                        offset: int = 0) -> list:
        if not isinstance(user_id, int):
            raise TypeError(f"Argument 'user_id' must be of type int, not {type(user_id)}.")

        if user_id <= 0:
            raise ValueError("Argument 'user_id' must be a positive, non-zero integer.")

        ret = []
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                SELECT 
                    e.*,
                    u.{ProtocolKey.USER}
                FROM 
                    {DatabaseTable.ENTRY} AS e
                LEFT JOIN (
                    SELECT
                        {ProtocolKey.ID},
                        ROW_TO_JSON(u) AS {ProtocolKey.USER}
                    FROM 
                        {DatabaseTable.USER} AS u
                ) AS u ON e.{ProtocolKey.USER_ID} = u.{ProtocolKey.ID}
                WHERE
                    e.{ProtocolKey.USER_ID} = %s
                ORDER BY
                    e.{ProtocolKey.CREATION_TIMESTAMP} DESC
                LIMIT
                    50 
                OFFSET
                    %s;
                """,
                (user_id, offset)
            )
            results = cursor.fetchall()
            db.connection.commit()
            for result in results:
                ret.append(cls(result))
        except Exception as e:
            print(e)
        finally:
            db.close()

        return ret

    @classmethod
    def get_by_id(cls: Type,
                  entry_id: uuid.UUID) -> T:
        if not isinstance(entry_id, uuid.UUID):
            raise TypeError(f"Argument 'entry_id' must be of type UUID, not {type(entry_id)}.")

        ret: Type = None
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                SELECT
                    *
                FROM
                    {DatabaseTable.ENTRY}
                WHERE
                    {ProtocolKey.ID} = %s;
                """,
                (entry_id,)
            )
            result = cursor.fetchone()
            db.connection.commit()
            if result:
                ret = cls(result)
        except Exception as e:
            print(e)
        finally:
            db.close()

        return ret

    @staticmethod
    def purge() -> None:
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                DELETE FROM
                    {DatabaseTable.ENTRY}
                WHERE
                    {ProtocolKey.CREATION_TIMESTAMP} < NOW() - INTERVAL '1 day' AND {ProtocolKey.USER_ID} IS NULL;
                """
            )
            db.connection.commit()
        except Exception as e:
            print(e)
        finally:
            db.close()


class EntryCoverImage:
    def __init__(self,
                 data: dict = {}) -> None:
        self.caption: str = None
        self.id: uuid.UUID = None
        self.source: str = None
        self.url: str = None

        if data:
            if ProtocolKey.CAPTION in data:
                self.caption: str = data[ProtocolKey.CAPTION]

            if ProtocolKey.ID in data:
                self.id: uuid.UUID = data[ProtocolKey.ID]

            if ProtocolKey.SOURCE in data:
                self.source: str = data[ProtocolKey.SOURCE]

            if ProtocolKey.URL in data:
                self.url: str = data[ProtocolKey.URL]

    def __eq__(self,
               __o: object) -> bool:
        ret = False
        if isinstance(__o, type(self)) and \
                self.url == __o.url:
            ret = True
        return ret

    def __hash__(self) -> int:
        return hash(self.url)

    def __repr__(self) -> str:
        ret = ""
        if self.id:
            ret += f"Entry Cover Image {self.url} ('{self.caption}')"
        return ret

    def as_dict(self) -> dict[str, str]:
        serialized = {}

        if self.caption:
            serialized[ProtocolKey.CAPTION] = self.caption

        if self.source:
            serialized[ProtocolKey.SOURCE] = self.source

        if self.url:
            serialized[ProtocolKey.URL] = self.url

        return serialized

    @classmethod
    def create(cls: Type,
               caption: str = None,
               entry_id: uuid.UUID = None,
               source: str = None,
               url: str = None) -> X:
        """
        Call this method to create an Entry Cover Image object.
        """

        if caption and not isinstance(caption, str):
            raise TypeError(f"Argument 'caption' must be of type str, not {type(caption)}.")

        if not isinstance(entry_id, uuid.UUID):
            raise TypeError(f"Argument 'entry_id' must be of type UUID, not {type(entry_id)}.")

        if source and not isinstance(source, str):
            raise TypeError(f"Argument 'source' must be of type str, not {type(source)}.")

        if not isinstance(url, str):
            raise TypeError(f"Argument 'url' must be of type str, not {type(url)}.")

        ret: Type = None
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                INSERT INTO
                    {DatabaseTable.ENTRY_COVER_IMAGE}
                    ({ProtocolKey.CAPTION}, {ProtocolKey.ENTRY_ID}, {ProtocolKey.SOURCE},
                     {ProtocolKey.URL})
                VALUES
                    (%s, %s, %s,
                     %s)
                RETURNING *;
                """,
                (caption, entry_id, source,
                 url)
            )
            result = cursor.fetchone()
            db.connection.commit()
            if result:
                ret = cls(result)
        except Exception as e:
            print(e)
        finally:
            db.close()

        return ret

    @classmethod
    def get_for_entry(cls: Type,
                      entry_id: uuid.UUID) -> X | None:
        if not isinstance(entry_id, uuid.UUID):
            raise TypeError(f"Argument 'entry_id' must be of type UUID, not {type(entry_id)}.")

        ret: X = None
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                SELECT 
                    *
                FROM 
                    {DatabaseTable.ENTRY_COVER_IMAGE}
                WHERE
                    {ProtocolKey.ENTRY_ID} = %s;
                """,
                (entry_id,)
            )
            result = cursor.fetchone()
            db.connection.commit()
            if result:
                ret = cls(result)
        except Exception as e:
            print(e)
        finally:
            db.close()

        return ret


class EntryFunFact:
    def __init__(self,
                 data: dict) -> None:
        self.content_md: str = None
        self.entry_id: uuid.UUID = None
        self.id: uuid.UUID = None

        if data:
            if ProtocolKey.CONTENT_MARKDOWN in data:
                self.content_md: str = data[ProtocolKey.CONTENT_MARKDOWN]

            if ProtocolKey.ENTRY_ID in data:
                self.entry_id: uuid.UUID = data[ProtocolKey.ENTRY_ID]

            if ProtocolKey.ID in data:
                self.id: uuid.UUID = data[ProtocolKey.ID]

    def __eq__(self,
               __o: object) -> bool:
        ret = False
        if isinstance(__o, type(self)) and \
                self.id == __o.id:
            ret = True
        return ret

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        ret = ""
        if self.id:
            ret += f"Entry Fun Fact {self.id} ('{self.content_md}')"
        return ret

    def as_dict(self) -> dict[str, str]:
        serialized = {
            ProtocolKey.ENTRY_ID: str(self.entry_id),
            ProtocolKey.ID: str(self.id),
            ProtocolKey.CONTENT_MARKDOWN: self.content_md
        }
        return serialized

    @classmethod
    def create(cls: Type,
               content_md: str = None,
               entry_id: uuid.UUID = None) -> U:
        """
        Call this method to create an Entry Fun Fact object.
        """

        if not isinstance(entry_id, uuid.UUID):
            raise TypeError(f"Argument 'entry_id' must be of type UUID, not {type(entry_id)}.")

        if not isinstance(content_md, str):
            raise TypeError(f"Argument 'content_md' must be of type str, not {type(content_md)}.")

        ret: Type = None
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                INSERT INTO
                    {DatabaseTable.ENTRY_FUN_FACT}
                    ({ProtocolKey.ENTRY_ID}, {ProtocolKey.CONTENT_MARKDOWN})
                VALUES
                    (%s, %s)
                RETURNING *;
                """,
                (entry_id, content_md)
            )
            result = cursor.fetchone()
            db.connection.commit()
            if result:
                ret = cls(result)
        except Exception as e:
            print(e)
        finally:
            db.close()

        return ret

    @classmethod
    def get_all_for_entry(cls: Type,
                          entry_id: uuid.UUID) -> list:
        if not isinstance(entry_id, uuid.UUID):
            raise TypeError(f"Argument 'entry_id' must be of type UUID, not {type(entry_id)}.")

        ret: list = []
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                SELECT 
                    *
                FROM 
                    {DatabaseTable.ENTRY_FUN_FACT}
                WHERE
                    {ProtocolKey.ENTRY_ID} = %s;
                """,
                (entry_id,)
            )
            results = cursor.fetchall()
            db.connection.commit()
            for result in results:
                ret.append(cls(result))
        except Exception as e:
            print(e)
        finally:
            db.close()

        return ret

    @classmethod
    def get_by_id(cls: Type,
                  fact_id: uuid.UUID) -> U:
        if not isinstance(fact_id, uuid.UUID):
            raise TypeError(f"Argument 'fact_id' must be of type UUID, not {type(fact_id)}.")

        ret: Type = None
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                SELECT
                    *
                FROM
                    {DatabaseTable.ENTRY_FUN_FACT}
                WHERE
                    {ProtocolKey.ID} = %s;
                """,
                (fact_id,)
            )
            result = cursor.fetchone()
            db.connection.commit()
            if result:
                ret = cls(result)
        except Exception as e:
            print(e)
        finally:
            db.close()

        return ret


class EntryRelatedTopic:
    def __init__(self,
                 data: dict) -> None:
        self.entry_id: uuid.UUID = None
        self.id: uuid.UUID = None
        self.topic: str = None

        if data:
            if ProtocolKey.ENTRY_ID in data:
                self.entry_id: uuid.UUID = data[ProtocolKey.ENTRY_ID]

            if ProtocolKey.ID in data:
                self.id: uuid.UUID = data[ProtocolKey.ID]

            if ProtocolKey.TOPIC in data:
                self.topic: str = data[ProtocolKey.TOPIC]

    def __eq__(self,
               __o: object) -> bool:
        ret = False
        if isinstance(__o, type(self)) and \
                self.id == __o.id:
            ret = True
        return ret

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        ret = ""
        if self.id:
            ret += f"Entry Related Topic {self.id} ('{self.topic}')"
        return ret

    def as_dict(self) -> dict[str, str]:
        serialized = {
            ProtocolKey.ENTRY_ID: str(self.entry_id),
            ProtocolKey.ID: str(self.id),
            ProtocolKey.TOPIC: self.topic
        }
        return serialized

    @classmethod
    def create(cls: Type,
               entry_id: uuid.UUID = None,
               topic: str = None) -> Y:
        """
        Call this method to create an Entry Related Topic object.
        """

        if not isinstance(entry_id, uuid.UUID):
            raise TypeError(f"Argument 'entry_id' must be of type UUID, not {type(entry_id)}.")

        if not isinstance(topic, str):
            raise TypeError(f"Argument 'topic' must be of type str, not {type(topic)}.")

        ret: Type = None
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                INSERT INTO
                    {DatabaseTable.ENTRY_RELATED_TOPIC}
                    ({ProtocolKey.ENTRY_ID}, {ProtocolKey.TOPIC})
                VALUES
                    (%s, %s)
                RETURNING *;
                """,
                (entry_id, topic)
            )
            result = cursor.fetchone()
            db.connection.commit()
            if result:
                ret = cls(result)
        except Exception as e:
            print(e)
        finally:
            db.close()

        return ret

    @classmethod
    def get_all_for_entry(cls: Type,
                          entry_id: uuid.UUID) -> list:
        if not isinstance(entry_id, uuid.UUID):
            raise TypeError(f"Argument 'entry_id' must be of type UUID, not {type(entry_id)}.")

        ret: list = []
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                SELECT 
                    *
                FROM 
                    {DatabaseTable.ENTRY_RELATED_TOPIC}
                WHERE
                    {ProtocolKey.ENTRY_ID} = %s;
                """,
                (entry_id,)
            )
            results = cursor.fetchall()
            db.connection.commit()
            for result in results:
                ret.append(cls(result))
        except Exception as e:
            print(e)
        finally:
            db.close()

        return ret

    @classmethod
    def get_by_id(cls: Type,
                  topic_id: uuid.UUID) -> U:
        if not isinstance(topic_id, uuid.UUID):
            raise TypeError(f"Argument 'topic_id' must be of type UUID, not {type(topic_id)}.")

        ret: Type = None
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                SELECT
                    *
                FROM
                    {DatabaseTable.ENTRY_RELATED_TOPIC}
                WHERE
                    {ProtocolKey.ID} = %s;
                """,
                (topic_id,)
            )
            result = cursor.fetchone()
            db.connection.commit()
            if result:
                ret = cls(result)
        except Exception as e:
            print(e)
        finally:
            db.close()

        return ret


class EntrySection:
    def __init__(self,
                 data: dict) -> None:
        self.content_html: str = None
        self.content_md: str = None
        self.entry_id: uuid.UUID = None
        self.id: uuid.UUID = None
        self.index: int = None
        self.parent_id: uuid.UUID = None
        self.subsections: list[EntrySection] = []
        self.title: str = None

        if data:
            if ProtocolKey.CONTENT_HTML in data:
                self.content_html: str = data[ProtocolKey.CONTENT_HTML]

            if ProtocolKey.CONTENT_MARKDOWN in data:
                self.content_md: str = data[ProtocolKey.CONTENT_MARKDOWN]

            if ProtocolKey.ENTRY_ID in data and data[ProtocolKey.ENTRY_ID]:
                if isinstance(data[ProtocolKey.ENTRY_ID], uuid.UUID):
                    self.entry_id: uuid.UUID = data[ProtocolKey.ENTRY_ID]
                else:
                    self.entry_id: uuid.UUID = uuid.UUID(data[ProtocolKey.ENTRY_ID])

            if ProtocolKey.ID in data and data[ProtocolKey.ID]:
                if isinstance(data[ProtocolKey.ID], uuid.UUID):
                    self.id: uuid.UUID = data[ProtocolKey.ID]
                else:
                    self.id: uuid.UUID = uuid.UUID(data[ProtocolKey.ID])

            if ProtocolKey.INDEX in data:
                self.index: int = data[ProtocolKey.INDEX]

            if ProtocolKey.PARENT_ID in data and data[ProtocolKey.PARENT_ID]:
                if isinstance(data[ProtocolKey.PARENT_ID], uuid.UUID):
                    self.parent_id: uuid.UUID = data[ProtocolKey.PARENT_ID]
                else:
                    self.parent_id: uuid.UUID = uuid.UUID(data[ProtocolKey.PARENT_ID])

            if ProtocolKey.SUBSECTIONS in data and data.get(ProtocolKey.SUBSECTIONS):
                subsections = data.get(ProtocolKey.SUBSECTIONS)
                for subsection in subsections:
                    self.subsections.append(EntrySection(subsection))

            if ProtocolKey.TITLE in data:
                self.title: str = data[ProtocolKey.TITLE]

    def __eq__(self,
               __o: object) -> bool:
        ret = False
        if isinstance(__o, type(self)) and \
                self.id == __o.id:
            ret = True
        return ret

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        ret = ""
        if self.id:
            ret += f"Entry Section {self.id} ('{self.title}')"
        return ret

    def as_dict(self,
                include_subsections=True) -> dict[str, Any]:
        serialized = {
            ProtocolKey.ENTRY_ID: str(self.entry_id),
            ProtocolKey.ID: str(self.id),
            ProtocolKey.INDEX: self.index,
            ProtocolKey.TITLE: self.title
        }

        if self.content_html:
            serialized[ProtocolKey.CONTENT_HTML] = self.content_html

        if self.content_md:
            serialized[ProtocolKey.CONTENT_MARKDOWN] = self.content_md

        if self.parent_id:
            serialized[ProtocolKey.PARENT_ID] = str(self.parent_id)

        if include_subsections and self.subsections:
            subsections_serialized = []
            for subsection in self.subsections:
                subsections_serialized.append(subsection.as_dict())
            serialized[ProtocolKey.SUBSECTIONS] = subsections_serialized

        return serialized

    @classmethod
    def create(cls: Type,
               content_html: str = None,
               content_md: str = None,
               entry_id: uuid.UUID = None,
               index: int = None,
               parent_id: uuid.UUID = None,
               title: str = None) -> V:
        """
        Call this method to create an Entry Section object.
        """

        if content_html and not isinstance(content_html, str):
            raise TypeError(f"Argument 'content_html' must be of type str, not {type(content_html)}.")

        if content_md and not isinstance(content_md, str):
            raise TypeError(f"Argument 'content_md' must be of type str, not {type(content_md)}.")

        if not isinstance(entry_id, uuid.UUID):
            raise TypeError(f"Argument 'entry_id' must be of type UUID, not {type(entry_id)}.")

        if not isinstance(index, int):
            raise TypeError(f"Argument 'index' must be of type int, not {type(index)}.")

        if parent_id and not isinstance(parent_id, uuid.UUID):
            raise TypeError(f"Argument 'parent_id' must be of type UUID, not {type(parent_id)}.")

        if not isinstance(title, str):
            raise TypeError(f"Argument 'title' must be of type str, not {type(title)}.")

        ret: Type = None
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                INSERT INTO
                    {DatabaseTable.ENTRY_SECTION}
                    ({ProtocolKey.CONTENT_HTML}, {ProtocolKey.CONTENT_MARKDOWN}, {ProtocolKey.ENTRY_ID},
                     {ProtocolKey.INDEX}, {ProtocolKey.PARENT_ID}, {ProtocolKey.TITLE})
                VALUES
                    (%s, %s, %s,
                     %s, %s, %s)
                RETURNING *;
                """,
                (content_html, content_md, entry_id,
                 index, parent_id, title)
            )
            result = cursor.fetchone()
            db.connection.commit()
            if result:
                ret = cls(result)
        except Exception as e:
            print(e)
        finally:
            db.close()

        return ret

    @classmethod
    def get_all_for_entry(cls: Type,
                          entry_id: uuid.UUID) -> list:
        if not isinstance(entry_id, uuid.UUID):
            raise TypeError(f"Argument 'entry_id' must be of type UUID, not {type(entry_id)}.")

        ret: list = []
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                WITH RECURSIVE section_hierarchy AS (
                  SELECT
                    {ProtocolKey.CONTENT_HTML},
                    {ProtocolKey.CONTENT_MARKDOWN},
                    {ProtocolKey.ENTRY_ID},
                    {ProtocolKey.ID},
                    {ProtocolKey.INDEX},
                    {ProtocolKey.PARENT_ID},
                    {ProtocolKey.TITLE},
                    jsonb_build_object(
                      '{ProtocolKey.CONTENT_HTML}', {ProtocolKey.CONTENT_HTML},
                      '{ProtocolKey.CONTENT_MARKDOWN}', {ProtocolKey.CONTENT_MARKDOWN},
                      '{ProtocolKey.ENTRY_ID}', {ProtocolKey.ENTRY_ID},
                      '{ProtocolKey.ID}', {ProtocolKey.ID},
                      '{ProtocolKey.INDEX}', {ProtocolKey.INDEX},
                      '{ProtocolKey.PARENT_ID}', {ProtocolKey.PARENT_ID},
                      '{ProtocolKey.SUBSECTIONS}', '[]'::jsonb,
                      '{ProtocolKey.TITLE}', {ProtocolKey.TITLE}
                    ) AS json_data,
                    1 AS depth
                  FROM
                    {DatabaseTable.ENTRY_SECTION}
                  WHERE
                    {ProtocolKey.PARENT_ID} IS NULL AND
                    {ProtocolKey.ENTRY_ID} = %s

                  UNION ALL

                  SELECT
                    c.{ProtocolKey.CONTENT_HTML},
                    c.{ProtocolKey.CONTENT_MARKDOWN},
                    c.{ProtocolKey.ENTRY_ID},
                    c.{ProtocolKey.ID},
                    c.{ProtocolKey.INDEX},
                    c.{ProtocolKey.PARENT_ID},
                    c.{ProtocolKey.TITLE},
                    jsonb_build_object(
                      '{ProtocolKey.CONTENT_HTML}', c.{ProtocolKey.CONTENT_HTML},
                      '{ProtocolKey.CONTENT_MARKDOWN}', c.{ProtocolKey.CONTENT_MARKDOWN},
                      '{ProtocolKey.ENTRY_ID}', c.{ProtocolKey.ENTRY_ID},
                      '{ProtocolKey.ID}', c.{ProtocolKey.ID},
                      '{ProtocolKey.INDEX}', c.{ProtocolKey.INDEX},
                      '{ProtocolKey.PARENT_ID}', c.{ProtocolKey.PARENT_ID},
                      '{ProtocolKey.SUBSECTIONS}', '[]'::jsonb,
                      '{ProtocolKey.TITLE}', c.{ProtocolKey.TITLE}
                    ),
                    sh.depth + 1
                  FROM
                    {DatabaseTable.ENTRY_SECTION} c
                  JOIN section_hierarchy sh ON sh.{ProtocolKey.ID} = c.{ProtocolKey.PARENT_ID}
                ),
                section_tree AS (
                  SELECT
                    *,
                    (
                      SELECT jsonb_agg(sh.json_data ORDER BY sh.{ProtocolKey.INDEX})
                      FROM section_hierarchy sh
                      WHERE sh.{ProtocolKey.PARENT_ID} = section_hierarchy.{ProtocolKey.ID}
                    ) AS {ProtocolKey.SUBSECTIONS}
                  FROM section_hierarchy
                  WHERE depth = 1
                )
                SELECT
                  jsonb_agg(
                    jsonb_set(
                      section_tree.json_data,
                      '{{{ProtocolKey.SUBSECTIONS}}}',
                      COALESCE(section_tree.{ProtocolKey.SUBSECTIONS}, '[]'::jsonb)
                    ) ORDER BY section_tree.{ProtocolKey.INDEX}
                  )
                FROM section_tree;
                """,
                (entry_id,)
            )
            results = cursor.fetchall()
            sections = results[0].get("jsonb_agg")
            db.connection.commit()
            if sections:
                for section in sections:
                    ret.append(cls(section))
        except Exception as e:
            print(e)
        finally:
            db.close()

        return ret

    @classmethod
    def get_by_id(cls: Type,
                  section_id: uuid.UUID) -> V:
        if not isinstance(section_id, uuid.UUID):
            raise TypeError(f"Argument 'section_id' must be of type UUID, not {type(section_id)}.")

        ret: Type = None
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                WITH RECURSIVE section_hierarchy AS (
                  SELECT
                    {ProtocolKey.CONTENT_HTML},
                    {ProtocolKey.CONTENT_MARKDOWN},
                    {ProtocolKey.ENTRY_ID},
                    {ProtocolKey.ID},
                    {ProtocolKey.INDEX},
                    {ProtocolKey.PARENT_ID},
                    {ProtocolKey.TITLE},
                    jsonb_build_object(
                      '{ProtocolKey.CONTENT_HTML}', {ProtocolKey.CONTENT_HTML},
                      '{ProtocolKey.CONTENT_MARKDOWN}', {ProtocolKey.CONTENT_MARKDOWN},
                      '{ProtocolKey.ENTRY_ID}', {ProtocolKey.ENTRY_ID},
                      '{ProtocolKey.ID}', {ProtocolKey.ID},
                      '{ProtocolKey.INDEX}', {ProtocolKey.INDEX},
                      '{ProtocolKey.PARENT_ID}', {ProtocolKey.PARENT_ID},
                      '{ProtocolKey.SUBSECTIONS}', '[]'::jsonb,
                      '{ProtocolKey.TITLE}', {ProtocolKey.TITLE}
                    ) AS json_data,
                    1 AS depth
                  FROM
                    {DatabaseTable.ENTRY_SECTION}
                  WHERE
                    {ProtocolKey.PARENT_ID} IS NULL AND
                    {ProtocolKey.ID} = %s

                  UNION ALL

                  SELECT
                    c.{ProtocolKey.CONTENT_HTML},
                    c.{ProtocolKey.CONTENT_MARKDOWN},
                    c.{ProtocolKey.ENTRY_ID},
                    c.{ProtocolKey.ID},
                    c.{ProtocolKey.INDEX},
                    c.{ProtocolKey.PARENT_ID},
                    c.{ProtocolKey.TITLE},
                    jsonb_build_object(
                      '{ProtocolKey.CONTENT_HTML}', c.{ProtocolKey.CONTENT_HTML},
                      '{ProtocolKey.CONTENT_MARKDOWN}', c.{ProtocolKey.CONTENT_MARKDOWN},
                      '{ProtocolKey.ENTRY_ID}', c.{ProtocolKey.ENTRY_ID},
                      '{ProtocolKey.ID}', c.{ProtocolKey.ID},
                      '{ProtocolKey.INDEX}', c.{ProtocolKey.INDEX},
                      '{ProtocolKey.PARENT_ID}', c.{ProtocolKey.PARENT_ID},
                      '{ProtocolKey.SUBSECTIONS}', '[]'::jsonb,
                      '{ProtocolKey.TITLE}', c.{ProtocolKey.TITLE}
                    ),
                    sh.depth + 1
                  FROM
                    {DatabaseTable.ENTRY_SECTION} c
                  JOIN section_hierarchy sh ON sh.{ProtocolKey.ID} = c.{ProtocolKey.PARENT_ID}
                ),
                section_tree AS (
                  SELECT
                    *,
                    (
                      SELECT jsonb_agg(sh.json_data ORDER BY sh.{ProtocolKey.INDEX})
                      FROM section_hierarchy sh
                      WHERE sh.{ProtocolKey.PARENT_ID} = section_hierarchy.{ProtocolKey.ID}
                    ) AS {ProtocolKey.SUBSECTIONS}
                  FROM section_hierarchy
                  WHERE depth = 1
                )
                SELECT
                  jsonb_agg(
                    jsonb_set(
                      section_tree.json_data,
                      '{{{ProtocolKey.SUBSECTIONS}}}',
                      COALESCE(section_tree.{ProtocolKey.SUBSECTIONS}, '[]'::jsonb)
                    ) ORDER BY section_tree.{ProtocolKey.INDEX}
                  )
                FROM section_tree;
                """,
                (section_id,)
            )
            result = cursor.fetchone()
            db.connection.commit()
            if result:
                result = result.get("jsonb_agg")[0]
                ret = cls(result)
        except Exception as e:
            print(e)
        finally:
            db.close()

        return ret

    def update(self) -> None:
        if not isinstance(self.id, uuid.UUID):
            raise TypeError(f"Section must have an existing ID in order to update.")

        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                UPDATE
                    {DatabaseTable.ENTRY_SECTION}
                SET
                    {ProtocolKey.CONTENT_HTML} = %s,
                    {ProtocolKey.CONTENT_MARKDOWN} = %s
                WHERE
                    {ProtocolKey.ID} = %s;
                """,
                (self.content_html, self.content_md, self.id)
            )
            db.connection.commit()
        except Exception as e:
            print(e)
        finally:
            db.close()


class EntryStat:
    def __init__(self,
                 data: dict) -> None:
        self.entry_id: uuid.UUID = None
        self.id: uuid.UUID = None
        self.index: int = None
        self.name_html: str = None
        self.name_md: str = None
        self.value_html: str = None
        self.value_md: str = None

        if data:
            if ProtocolKey.ENTRY_ID in data:
                self.entry_id: uuid.UUID = data[ProtocolKey.ENTRY_ID]

            if ProtocolKey.ID in data:
                self.id: uuid.UUID = data[ProtocolKey.ID]

            if ProtocolKey.INDEX in data:
                self.index: int = data[ProtocolKey.INDEX]

            if ProtocolKey.NAME_HTML in data:
                self.name_html: str = data[ProtocolKey.NAME_HTML]

            if ProtocolKey.NAME_MARKDOWN in data:
                self.name_md: str = data[ProtocolKey.NAME_MARKDOWN]

            if ProtocolKey.VALUE_HTML in data:
                self.value_html: str = data[ProtocolKey.VALUE_HTML]

            if ProtocolKey.VALUE_MARKDOWN in data:
                self.value_md: str = data[ProtocolKey.VALUE_MARKDOWN]

    def __eq__(self,
               __o: object) -> bool:
        ret = False
        if isinstance(__o, type(self)) and \
                self.id == __o.id:
            ret = True
        return ret

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        ret = ""
        if self.id:
            ret += f"Entry Stat {self.id} ('{self.name_md}: {self.value_md}')"
        return ret

    def as_dict(self) -> dict[str, str]:
        serialized = {
            ProtocolKey.ENTRY_ID: str(self.entry_id),
            ProtocolKey.ID: str(self.id),
            ProtocolKey.INDEX: self.index,
            ProtocolKey.NAME_HTML: self.name_html,
            ProtocolKey.NAME_MARKDOWN: self.name_md,
            ProtocolKey.VALUE_HTML: self.value_html,
            ProtocolKey.VALUE_MARKDOWN: self.value_md
        }
        return serialized

    @classmethod
    def create(cls: Type,
               entry_id: uuid.UUID = None,
               index: int = None,
               name_html: str = None,
               name_md: str = None,
               value_html: str = None,
               value_md: str = None) -> W:
        """
        Call this method to create an Entry Stat object.
        """

        if not isinstance(entry_id, uuid.UUID):
            raise TypeError(f"Argument 'entry_id' must be of type UUID, not {type(entry_id)}.")

        if not isinstance(index, int):
            raise TypeError(f"Argument 'index' must be of type int, not {type(index)}.")

        if not isinstance(name_html, str):
            raise TypeError(f"Argument 'name_html' must be of type str, not {type(name_html)}.")

        if not isinstance(name_md, str):
            raise TypeError(f"Argument 'name_md' must be of type str, not {type(name_md)}.")

        if not isinstance(value_html, str):
            raise TypeError(f"Argument 'value_html' must be of type str, not {type(value_html)}.")

        if not isinstance(value_md, str):
            raise TypeError(f"Argument 'value_md' must be of type str, not {type(value_md)}.")

        ret: Type = None
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                INSERT INTO
                    {DatabaseTable.ENTRY_STAT}
                    ({ProtocolKey.ENTRY_ID}, {ProtocolKey.INDEX}, {ProtocolKey.NAME_HTML},
                     {ProtocolKey.NAME_MARKDOWN}, {ProtocolKey.VALUE_HTML}, {ProtocolKey.VALUE_MARKDOWN})
                VALUES
                    (%s, %s, %s,
                     %s, %s, %s)
                RETURNING *;
                """,
                (entry_id, index, name_html,
                 name_md, value_html, value_md)
            )
            result = cursor.fetchone()
            db.connection.commit()
            if result:
                ret = cls(result)
        except Exception as e:
            print(e)
        finally:
            db.close()

        return ret

    @classmethod
    def get_all_for_entry(cls: Type,
                          entry_id: uuid.UUID) -> list:
        if not isinstance(entry_id, uuid.UUID):
            raise TypeError(f"Argument 'entry_id' must be of type UUID, not {type(entry_id)}.")

        ret: list = []
        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                SELECT 
                    *
                FROM 
                    {DatabaseTable.ENTRY_STAT}
                WHERE
                    {ProtocolKey.ENTRY_ID} = %s;
                """,
                (entry_id,)
            )
            results = cursor.fetchall()
            db.connection.commit()
            for result in results:
                ret.append(cls(result))
        except Exception as e:
            print(e)
        finally:
            db.close()

        return ret


chat_histories = {}


####################
# MODULE FUNCTIONS #
####################


def get_entry(session_id: str,
              entry_id: uuid.UUID) -> tuple[dict, ResponseStatus]:
    if not entry_id:
        response_status = ResponseStatus.BAD_REQUEST
        response = {
            ProtocolKey.ERROR: {
                ProtocolKey.ERROR_CODE: response_status.value,
                ProtocolKey.ERROR_MESSAGE: "Missing or badly-formed argument: 'entry_id'."
            }
        }
    else:
        entry: Entry = Entry.get_by_id(entry_id)
        if entry:
            response_status = ResponseStatus.OK
            response = entry.as_dict()
        else:
            response_status = ResponseStatus.NOT_FOUND
            response = {
                ProtocolKey.ERROR: {
                    ProtocolKey.ERROR_CODE: response_status.value,
                    ProtocolKey.ERROR_MESSAGE: "No entry exists for the given ID."
                }
            }

    return (response, response_status)


def get_entries(session_id: str) -> tuple[list, ResponseStatus]:
    if session_id:
        response_status = ResponseStatus.OK
        session: UserSession = UserSession.get_by_id(session_id)
        user_id = session.user_id
        entries = Entry.get_all_by_user(user_id)
        entries_serialized = []
        for chat in entries:
            entries_serialized.append(chat.as_dict())
        response = entries_serialized
    else:
        response_status = ResponseStatus.BAD_REQUEST
        response = {
            ProtocolKey.ERROR: {
                ProtocolKey.ERROR_CODE: ResponseStatus.BAD_REQUEST.value,
                ProtocolKey.ERROR_MESSAGE: "Missing session ID."
            }
        }

    return (response, response_status)


def get_cover_image(entry_id: uuid.UUID) -> Iterator[str]:
    if not entry_id:
        response_status = ResponseStatus.BAD_REQUEST
        response = {
            ProtocolKey.ERROR: {
                ProtocolKey.ERROR_CODE: response_status.value,
                ProtocolKey.ERROR_MESSAGE: "Missing argument: 'entry_id'."
            }
        }
        yield f"data: {json.dumps(response)}\n\n"
        yield "event: close\n\n"
    else:
        entry: Entry = Entry.get_by_id(entry_id)
        if entry and not entry.cover_image:
            query = entry.topic
            params = {
                "engine": "google_images",
                "q": query,
                "api_key": Configuration.SERPAPI_API_KEY
            }

            search = GoogleSearch(params)
            results = search.get_dict()
            if results:
                results: list[dict] = results.get("images_results")
                if results:
                    image_data = results[0]
                    caption = image_data["title"]
                    source = image_data["source"]
                    url = image_data["original"]

                    image: EntryCoverImage = EntryCoverImage.create(
                        caption=caption,
                        entry_id=entry_id,
                        source=source,
                        url=url
                    )
                    if image:
                        yield f"data: {json.dumps(image.as_dict())}\n\n"

            yield "event: close\n\n"
        else:
            response_status = ResponseStatus.NOT_FOUND
            response = {
                ProtocolKey.ERROR: {
                    ProtocolKey.ERROR_CODE: response_status.value,
                    ProtocolKey.ERROR_MESSAGE: "No entry exists for the given ID."
                }
            }
            yield f"data: {json.dumps(response)}\n\n"
            yield "event: close\n\n"


def get_related_topics(entry_id: uuid.UUID) -> Iterator[str]:
    if not entry_id:
        response_status = ResponseStatus.BAD_REQUEST
        response = {
            ProtocolKey.ERROR: {
                ProtocolKey.ERROR_CODE: response_status.value,
                ProtocolKey.ERROR_MESSAGE: "Missing argument: 'entry_id'."
            }
        }
        yield f"data: {json.dumps(response)}\n\n"
        yield "event: close\n\n"
    else:
        entry: Entry = Entry.get_by_id(entry_id)
        if entry:
            if not entry.related_topics:
                related_topics = gpt.get_entry_related_topics(
                    proficiency=entry.proficiency.prompt_format(),
                    topic=entry.topic
                )
                if related_topics:
                    for related_topic in related_topics:
                        topic: EntryRelatedTopic = EntryRelatedTopic.create(
                            entry_id=entry_id,
                            topic=related_topic
                        )
                        if topic:
                            yield f"data: {json.dumps(topic.as_dict())}\n\n"
            else:
                response_status = ResponseStatus.ALREADY_EXISTS
                response = {
                    ProtocolKey.ERROR: {
                        ProtocolKey.ERROR_CODE: response_status.value,
                        ProtocolKey.ERROR_MESSAGE: "This entry's related topics have already been created."
                    }
                }
                yield f"data: {json.dumps(response)}\n\n"

            yield "event: close\n\n"
        else:
            response_status = ResponseStatus.NOT_FOUND
            response = {
                ProtocolKey.ERROR: {
                    ProtocolKey.ERROR_CODE: response_status.value,
                    ProtocolKey.ERROR_MESSAGE: "No entry exists for the given ID."
                }
            }
            yield f"data: {json.dumps(response)}\n\n"
            yield "event: close\n\n"


def make(session_id: str,
         proficiency: UserTopicProficiency = UserTopicProficiency.INTERMEDIATE,
         user_topic: str = None) -> tuple[dict, ResponseStatus]:
    if user_topic:
        user_topic = user_topic.strip()
    else:
        user_topic = None

    if not user_topic:
        response_status = ResponseStatus.BAD_REQUEST
        error_message = "An entry must have a topic."
        response = {
            ProtocolKey.ERROR: {
                ProtocolKey.ERROR_CODE: response_status.value,
                ProtocolKey.ERROR_MESSAGE: error_message
            }
        }
    else:
        response_status = ResponseStatus.CREATED

        if len(user_topic) > Configuration.TOPIC_MAX_LEN:
            response_status = ResponseStatus.BAD_REQUEST
            response = {
                ProtocolKey.ERROR: {
                    ProtocolKey.ERROR_CODE: ResponseStatus.CONTENT_MAX_LEN_EXCEEDED.value,
                    ProtocolKey.ERROR_MESSAGE: "Topic exceeds maximum length allowed."
                }
            }

        if response_status == ResponseStatus.CREATED:
            creator = User.get_by_session(session_id)

            if creator:
                creator_id = creator.id
            else:
                creator_id = None

            md_extension_configs = {
                "pymdownx.highlight": {
                    "auto_title": True,
                    "auto_title_map": {
                        "Python Console Session": "Python"
                    }
                }
            }

            # Get a proper topic from the LLM.
            topic = gpt.get_entry_topic(user_topic)
            if topic:
                topic = util.unquote(topic)  # Sometimes the LLM returns the topic enclosed in quotes.
                summary = gpt.get_entry_summary(topic)
                entry: Entry = Entry.create(
                    proficiency=proficiency,
                    summary=summary,
                    topic=topic,
                    user_id=creator_id
                )
                if entry:
                    AnalyticsTopicHistory.create(user_topic)

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        facts_future = executor.submit(gpt.get_entry_fun_facts, topic)
                        stats_future = executor.submit(gpt.get_entry_stats, topic)

                        facts_raw = facts_future.result()
                        stats_raw = stats_future.result()

                        if facts_raw:
                            for fact in facts_raw:
                                EntryFunFact.create(fact, entry.id)

                        if stats_raw:
                            for i, stat in enumerate(stats_raw):
                                name_md, value_md = stat.popitem()

                                name_html = markdown.markdown(
                                    name_md,
                                    extensions=["pymdownx.superfences"],
                                    extension_configs=md_extension_configs
                                )
                                value_html = markdown.markdown(
                                    value_md,
                                    extensions=["pymdownx.superfences"],
                                    extension_configs=md_extension_configs
                                )
                                EntryStat.create(
                                    entry_id=entry.id,
                                    index=i,
                                    name_html=name_html,
                                    name_md=name_md,
                                    value_html=value_html,
                                    value_md=value_md
                                )

                        response = {ProtocolKey.ID: entry.id}
            else:
                if topic == "":
                    response_status = ResponseStatus.NOT_FOUND
                    error_message = "Unknown topic."
                    response = {
                        ProtocolKey.ERROR: {
                            ProtocolKey.ERROR_CODE: response_status.value,
                            ProtocolKey.ERROR_MESSAGE: error_message
                        }
                    }
                else:
                    response_status = ResponseStatus.NOT_ALLOWED
                    error_message = "This topic contains or implies content that falls outside acceptable use guidelines."
                    response = {
                        ProtocolKey.ERROR: {
                            ProtocolKey.ERROR_CODE: response_status.value,
                            ProtocolKey.ERROR_MESSAGE: error_message
                        }
                    }

    return (response, response_status)


def make_chat_completion(context: str,
                         entry_id: uuid.UUID,
                         reset_chat: bool,
                         section_id: uuid.UUID,
                         session_id: str,
                         user_query_md: str) -> Iterator[str]:
    if not entry_id:
        response_status = ResponseStatus.BAD_REQUEST
        response = {
            ProtocolKey.ERROR: {
                ProtocolKey.ERROR_CODE: response_status.value,
                ProtocolKey.ERROR_MESSAGE: "Missing argument: 'entry_id'."
            }
        }
        yield f"data: {json.dumps(response)}\n\n"
        yield "event: close\n\n"
    else:
        entry: Entry = Entry.get_by_id(entry_id)
        if entry:
            user_query_md = user_query_md.strip()

            if user_query_md:
                section: EntrySection = EntrySection.get_by_id(section_id)
                if not section:
                    # Might be a selection in a fun fact.
                    section: EntryFunFact = EntryFunFact.get_by_id(section_id)

                creator = User.get_by_session(session_id)

                if creator:
                    creator_id = creator.id
                else:
                    creator_id = None

                history = chat_histories.get(section_id)
                if not history or reset_chat:
                    history = []
                    chat_histories[section_id] = history

                md_extension_configs = {
                    "pymdownx.highlight": {
                        "auto_title": True,
                        "auto_title_map": {
                            "Python Console Session": "Python"
                        }
                    }
                }
                user_query_html = markdown.markdown(
                    user_query_md,
                    extensions=["pymdownx.superfences", "tables"],
                    extension_configs=md_extension_configs
                )

                user_message = ChatMessage()
                user_message.chat_id = section_id
                user_message.content_html = user_query_html
                user_message.content_md = user_query_md
                user_message.sender_id = creator_id
                user_message.sender_role = ChatMessageSenderRole.USER
                history.append(user_message)

                response_md = gpt.get_entry_chat_completion(
                    context=context,
                    messages=history,
                    proficiency=entry.proficiency.prompt_format(),
                    section_md=section.content_md,
                    topic=entry.topic
                )
                response_html = markdown.markdown(
                    response_md,
                    extensions=["footnotes", "pymdownx.superfences", "tables"],
                    extension_configs=md_extension_configs
                )

                llm_message = ChatMessage()
                llm_message.chat_id = section_id
                llm_message.content_html = response_html
                llm_message.content_md = response_md
                llm_message.sender_role = ChatMessageSenderRole.ASSISTANT
                history.append(llm_message)

                yield f"data: {response_html}\n\n"
                yield "event: close\n\n"
            else:
                yield "event: close\n\n"
        else:
            response_status = ResponseStatus.NOT_FOUND
            response = {
                ProtocolKey.ERROR: {
                    ProtocolKey.ERROR_CODE: response_status.value,
                    ProtocolKey.ERROR_MESSAGE: "No entry exists for the given ID."
                }
            }
            yield f"data: {json.dumps(response)}\n\n"
            yield "event: close\n\n"


def make_section(section_id: uuid.UUID) -> Iterator[str]:
    if not section_id:
        response_status = ResponseStatus.BAD_REQUEST
        response = {
            ProtocolKey.ERROR: {
                ProtocolKey.ERROR_CODE: response_status.value,
                ProtocolKey.ERROR_MESSAGE: "Missing argument: 'section_id'."
            }
        }
        yield f"data: {json.dumps(response)}\n\n"
        yield "event: close\n\n"
    else:
        section: EntrySection = EntrySection.get_by_id(section_id)
        if section:
            if not section.content_html:
                entry: Entry = Entry.get_by_id(section.entry_id)
                if entry:
                    md_extension_configs = {
                        "pymdownx.highlight": {
                            "auto_title": True,
                            "auto_title_map": {
                                "Python Console Session": "Python"
                            }
                        }
                    }

                    content_md = gpt.get_entry_section(
                        proficiency=entry.proficiency.prompt_format(),
                        section_title=section.title,
                        topic=entry.topic
                    )
                    if content_md:
                        content_html = markdown.markdown(
                            content_md,
                            extensions=["footnotes", "pymdownx.superfences", "tables"],
                            extension_configs=md_extension_configs
                        )
                        section.content_html = content_html
                        section.content_md = content_md

                        yield f"data: {json.dumps(section.as_dict())}\n\n"
                        section.update()

                        for subsection in section.subsections:
                            subtitle = subsection.title

                            content_md = gpt.get_entry_section(
                                proficiency=entry.proficiency.prompt_format(),
                                section_title=subtitle,
                                topic=entry.topic
                            )

                            if content_md:
                                content_html = markdown.markdown(
                                    content_md,
                                    extensions=["footnotes", "pymdownx.superfences", "tables"],
                                    extension_configs=md_extension_configs
                                )

                            subsection.content_html = content_html
                            subsection.content_md = content_md

                            yield f"data: {json.dumps(subsection.as_dict())}\n\n"
                            subsection.update()
                    else:
                        response_status = ResponseStatus.NO_CONTENT
                        response = {
                            ProtocolKey.ERROR: {
                                ProtocolKey.ERROR_CODE: response_status.value,
                                ProtocolKey.ERROR_MESSAGE: "There was an error generating this section."
                            }
                        }
                        yield f"data: {json.dumps(response)}\n\n"
                else:
                    response_status = ResponseStatus.NOT_FOUND
                    response = {
                        ProtocolKey.ERROR: {
                            ProtocolKey.ERROR_CODE: response_status.value,
                            ProtocolKey.ERROR_MESSAGE: "No entry exists for the given section ID."
                        }
                    }
                    yield f"data: {json.dumps(response)}\n\n"

                yield "event: close\n\n"
            else:
                response_status = ResponseStatus.ALREADY_EXISTS
                response = {
                    ProtocolKey.ERROR: {
                        ProtocolKey.ERROR_CODE: response_status.value,
                        ProtocolKey.ERROR_MESSAGE: "This section has already been created."
                    }
                }
                yield f"data: {json.dumps(response)}\n\n"
                yield "event: close\n\n"
        else:
            response_status = ResponseStatus.NOT_FOUND
            response = {
                ProtocolKey.ERROR: {
                    ProtocolKey.ERROR_CODE: response_status.value,
                    ProtocolKey.ERROR_MESSAGE: "No section exists for the given ID."
                }
            }
            yield f"data: {json.dumps(response)}\n\n"
            yield "event: close\n\n"


def make_sections(entry_id: uuid.UUID) -> Iterator[str]:
    """
    For generating the ToC and the first section.
    """

    if not entry_id:
        response_status = ResponseStatus.BAD_REQUEST
        response = {
            ProtocolKey.ERROR: {
                ProtocolKey.ERROR_CODE: response_status.value,
                ProtocolKey.ERROR_MESSAGE: "Missing argument: 'entry_id'."
            }
        }
        yield f"data: {json.dumps(response)}\n\n"
        yield "event: close\n\n"
    else:
        entry: Entry = Entry.get_by_id(entry_id)
        if entry:
            if not entry.sections:
                md_extension_configs = {
                    "pymdownx.highlight": {
                        "auto_title": True,
                        "auto_title_map": {
                            "Python Console Session": "Python"
                        }
                    }
                }

                toc = gpt.get_entry_table_of_contents(
                    proficiency=entry.proficiency.prompt_format(),
                    topic=entry.topic
                )
                if toc:
                    for i, section_raw in enumerate(toc):
                        title = section_raw.get("title")

                        # Only fetch the content of the first section. The rest are lazy-loaded.
                        if i == 0:
                            content_md = gpt.get_entry_section(
                                proficiency=entry.proficiency.prompt_format(),
                                section_title=title,
                                topic=entry.topic
                            )
                        else:
                            content_md = None

                        if content_md:
                            content_html = markdown.markdown(
                                content_md,
                                extensions=["footnotes", "pymdownx.superfences", "tables"],
                                extension_configs=md_extension_configs
                            )
                        else:
                            content_html = None

                        section: EntrySection = EntrySection.create(
                            content_html=content_html,
                            content_md=content_md,
                            entry_id=entry.id,
                            index=i,
                            title=title
                        )

                        yield f"data: {json.dumps(section.as_dict())}\n\n"

                        subsections: list[dict] = section_raw.get("subsections")
                        if subsections:
                            for j, subsection_raw in enumerate(subsections):
                                subtitle = subsection_raw.get("title")

                                if i == 0:
                                    content_md = gpt.get_entry_section(
                                        proficiency=entry.proficiency.prompt_format(),
                                        section_title=subtitle,
                                        topic=entry.topic
                                    )
                                else:
                                    content_md = None

                                if content_md:
                                    content_html = markdown.markdown(
                                        content_md,
                                        extensions=["footnotes", "pymdownx.superfences", "tables"],
                                        extension_configs=md_extension_configs
                                    )
                                else:
                                    content_html = None

                                subsection: EntrySection = EntrySection.create(
                                    content_html=content_html,
                                    content_md=content_md,
                                    entry_id=entry.id,
                                    index=j,
                                    parent_id=section.id,
                                    title=subtitle
                                )

                                yield f"data: {json.dumps(subsection.as_dict())}\n\n"
                else:
                    response_status = ResponseStatus.NO_CONTENT
                    response = {
                        ProtocolKey.ERROR: {
                            ProtocolKey.ERROR_CODE: response_status.value,
                            ProtocolKey.ERROR_MESSAGE: "There was an error generating sections."
                        }
                    }
                    yield f"data: {json.dumps(response)}\n\n"

                yield "event: close\n\n"
            else:
                response_status = ResponseStatus.ALREADY_EXISTS
                response = {
                    ProtocolKey.ERROR: {
                        ProtocolKey.ERROR_CODE: response_status.value,
                        ProtocolKey.ERROR_MESSAGE: "This entry has already been created."
                    }
                }
                yield f"data: {json.dumps(response)}\n\n"
                yield "event: close\n\n"
        else:
            response_status = ResponseStatus.NOT_FOUND
            response = {
                ProtocolKey.ERROR: {
                    ProtocolKey.ERROR_CODE: response_status.value,
                    ProtocolKey.ERROR_MESSAGE: "No entry exists for the given ID."
                }
            }
            yield f"data: {json.dumps(response)}\n\n"
            yield "event: close\n\n"


def remove(session_id: str,
           entry_id: uuid.UUID) -> tuple[dict, ResponseStatus]:
    if not entry_id:
        response_status = ResponseStatus.BAD_REQUEST
        response = {
            ProtocolKey.ERROR: {
                ProtocolKey.ERROR_CODE: response_status.value,
                ProtocolKey.ERROR_MESSAGE: "Missing argument: 'entry_id'."
            }
        }
    else:
        entry: Entry = Entry.get_by_id(entry_id)
        if entry:
            current_account = User.get_by_session(session_id)
            if current_account and current_account.id == entry.user_id:
                entry.delete()
                response_status = ResponseStatus.NO_CONTENT
                response = {}
            else:
                response_status = ResponseStatus.UNAUTHORIZED
                response = {
                    ProtocolKey.ERROR: {
                        ProtocolKey.ERROR_CODE: response_status.value,
                        ProtocolKey.ERROR_MESSAGE: "Only the entry creator can delete their entry."
                    }
                }
        else:
            response_status = ResponseStatus.NOT_FOUND
            response = {
                ProtocolKey.ERROR: {
                    ProtocolKey.ERROR_CODE: response_status.value,
                    ProtocolKey.ERROR_MESSAGE: "No entry exists for the given ID."
                }
            }

    return (response, response_status)


entry_purge_scheduled_task = EntryPurgeJob()
entry_purge_scheduled_task.start()
