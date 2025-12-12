import psycopg

from usbipice.control import ControlDatabase

class ServerDatabase(ControlDatabase):
    """Provides methods for accessing the database related to the control process."""
    def reserve(self, amount: int, clientname: str) -> dict:
        """Reserves amount devices for clientname. Returns as {serial, ip, serverport}"""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM makeReservations(%s::int, %s::varchar(255), %s::varchar(255))", (amount, clientname))

                    data = cur.fetchall()
        except Exception:
            return False

        values = []
        for row in data:
            values.append({
                "serial": row[0],
                "ip": str(row[1]),
                "serverport": row[2]
            })

        return values

    def extend(self, name: str, serials: list[str]) -> list[str]:
        """Extends the reservation time of the serials under the name of the client. Returns the extended serials"""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM extendReservations(%s::varchar(255), %s::varchar(255)[])", (name, serials))

                    data = cur.fetchall()
        except Exception:
            return False

        return data

    def extendAll(self, name: str) -> list[str]:
        """Extends the reservation time of all serials under the name of the client. Returns the extended serials."""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM extendAllReservations(%s::varchar(255))", (name,))

                    data = cur.fetchall()
        except Exception:
            return False

        return data

    def end(self, name: str, serials: list[str]):
        """Ends the reservation of serials under the name of the client.
        Returns as {serial, subscriptionurl, workerip, workerport}"""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM endReservations(%s::varchar(255), %s::varchar(255)[])", (name, serials))

                    data = cur.fetchall()
        except Exception:
            return False

        values = []
        for row in data:
            values.append({
                "serial": row[0],
                "subscriptionurl": row[1],
                "workerip": str(row[2]),
                "workerport": str(row[3])
            })

        return values

    def endAll(self, name: str):
        """Ends all of the reservations under the client name.
        Returns as {serial, subscriptionurl, workerip, workerport}"""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM endAllReservations(%s::varchar(255))", (name,))

                    data = cur.fetchall()
        except Exception:
            return False

        values = []
        for row in data:
            values.append({
                "serial": row[0],
                "subscriptionurl": row[1],
                "workerip": str(row[2]),
                "workerport": str(row[3])
            })

        return values
