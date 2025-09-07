import os, sqlite3, time, random
DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "breachit.db")

schema = """
DROP TABLE IF EXISTS Users;
DROP TABLE IF EXISTS Products;
DROP TABLE IF EXISTS Orders;
DROP TABLE IF EXISTS OrderItems;
DROP TABLE IF EXISTS Reviews;
DROP TABLE IF EXISTS Breaches;

CREATE TABLE Users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL,
  email TEXT NOT NULL
);

CREATE TABLE Products(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  price REAL NOT NULL
);

CREATE TABLE Orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  total_amount REAL NOT NULL,
  created_at INTEGER NOT NULL,
  FOREIGN KEY(user_id) REFERENCES Users(id)
);

CREATE TABLE OrderItems(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  quantity INTEGER NOT NULL,
  unit_price REAL NOT NULL,
  FOREIGN KEY(order_id) REFERENCES Orders(id),
  FOREIGN KEY(product_id) REFERENCES Products(id)
);

CREATE TABLE Reviews(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL,
  rating INTEGER NOT NULL,
  title TEXT,
  body TEXT,
  FOREIGN KEY(product_id) REFERENCES Products(id)
);

CREATE TABLE Breaches(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  authorized_id TEXT NOT NULL,
  user_sql TEXT NOT NULL,
  reason TEXT NOT NULL,
  is_superset INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  meta_json TEXT
);
"""

users = [
    ("alice", "alice@example.com"),
    ("bob", "bob@example.com"),
    ("carol", "carol@example.com"),
]

products = [
    ("Keyboard", 49.99),
    ("Mouse", 19.99),
    ("Monitor", 199.99),
    ("USB-C Cable", 9.99),
    ("Webcam", 59.99),
]

def main():
    os.makedirs(DB_DIR, exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(schema)

    cur.executemany("INSERT INTO Users(username,email) VALUES(?,?)", users)
    cur.executemany("INSERT INTO Products(name,price) VALUES(?,?)", products)

    # Create orders for users
    now = int(time.time())
    oid = 1
    for uid in range(1, 4):  # users 1..3
        for _ in range(2):
            total = 0.0
            cur.execute("INSERT INTO Orders(user_id,total_amount,created_at) VALUES(?,?,?)", (uid, 0.0, now))
            order_id = cur.lastrowid
            # add 2 items
            for _ in range(2):
                pid = random.randint(1, len(products))
                qty = random.randint(1, 3)
                price = products[pid-1][1]
                total += qty * price
                cur.execute("INSERT INTO OrderItems(order_id,product_id,quantity,unit_price) VALUES(?,?,?,?)",
                            (order_id, pid, qty, price))
            cur.execute("UPDATE Orders SET total_amount=? WHERE id=?", (round(total,2), order_id))

    # Reviews
    for pid in range(1, len(products)+1):
        cur.execute("INSERT INTO Reviews(product_id,rating,title,body) VALUES(?,?,?,?)",
                    (pid, random.randint(3,5), f"Review for {pid}", "Solid product."))

    conn.commit()
    conn.close()
    print("Database created and seeded at", DB_PATH)

if __name__ == "__main__":
    main()
