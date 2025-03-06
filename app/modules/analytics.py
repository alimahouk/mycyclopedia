from app.config import DatabaseTable, ProtocolKey
from app.modules.db import RelationalDB


###########
# CLASSES #
###########


class AnalyticsTopicHistory:
    @staticmethod
    def create(topic: str) -> None:
        """
        Call this method to log a user's topic query.
        """

        if not isinstance(topic, str):
            raise TypeError(f"Argument 'topic' must be of type str, not {type(topic)}.")

        db = RelationalDB()
        try:
            cursor = db.connection.cursor()
            cursor.execute(
                f"""
                INSERT INTO
                    {DatabaseTable.ANALYTICS_TOPIC_HISTORY}
                    ({ProtocolKey.TOPIC})
                VALUES
                    (%s);
                """,
                (topic,)
            )
            db.connection.commit()
        except Exception as e:
            print(e)
        finally:
            db.close()
