
import os
from flask import Flask, render_template, request, session, redirect, url_for
import requests
from flask_bcrypt import Bcrypt
from db import get_db_connection

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
bcrypt = Bcrypt(app)


@app.route("/")
def home():
    query = request.args.get("q", "").strip()
    genre = request.args.get("genre", "").strip()
    books = []
    error = None
    recommended_genres = []
    user_ratings = {}

    
    if "user_id" in session:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT book_key, rating
                FROM ratings
                WHERE user_id = %s
                """,
                (session["user_id"],)
            )
            user_ratings = {
            row["book_key"]: row["rating"]
            for row in cursor.fetchall()
            }
            cursor.execute(
                """
                SELECT book_title, rating
                FROM ratings
                WHERE user_id = %s AND rating >= 4
                """,
                (session["user_id"],)
            )
            favorite_books = cursor.fetchall()
            print("Favorite books:", favorite_books)
            
            for favorite in favorite_books:
                try:
                   response = requests.get(
                       "https://openlibrary.org/search.json",
                       params={"title": favorite["book_title"], "limit": 5, "fields": "title,author_name,subject"},
                       timeout=10
                    )
                   response.raise_for_status()
                   results = response.json().get("docs", [])
                   if not results:
                       continue
                   
                   subjects = results[0].get("subject", [])
                   print(
                    "Book:", favorite["book_title"],
                    "| Subjects:", subjects[:10]
                   )
                   for subject in subjects:
                       subject = subject.lower()

                       if any(word in subject for word in [
                           "romance", "love stories"
                       ]):
                            recommended_genres.append("romance")
                       elif "fantasy" in subject:
                            recommended_genres.append("fantasy")
                       elif "dystop" in subject:
                            recommended_genres.append("dystopian")
                       elif "science fiction" in subject:
                            recommended_genres.append("science fiction")
                       elif "thriller" in subject:
                            recommended_genres.append("thriller")
                       elif "mystery" in subject or "detective" in subject:
                            recommended_genres.append("mystery")
                       elif "horror" in subject:
                            recommended_genres.append("horror")
                       elif "historical fiction" in subject:
                            recommended_genres.append("historical fiction")
                       elif "young adult" in subject:
                            recommended_genres.append("young adult")
                       elif "poetry" in subject:
                            recommended_genres.append("poetry")
                       elif "biography" in subject:
                            recommended_genres.append("biography")

                except requests.RequestException:
                    continue

            recommended_genres = list(dict.fromkeys(recommended_genres))
            print("Recommended genres:", recommended_genres)
        finally:
            cursor.close()
            connection.close()
    else:
        favorite_books = []


    # Show recommendations on the homepage
    if genre:
      searches = [f"subject:{genre}"]
    elif query:
      searches = [query]

    if genre:
        if genre == "fiction":
            searches = ["subject:fiction OR subject:novel"]
        elif genre == "nonfiction":
              searches = ["subject:nonfiction"]
        else:
            searches = [f"subject:{genre}"]
    elif query:
        searches = [query]
    elif recommended_genres and "user_id" in session:
        searches = [
            f"subject:{book_genre}"
            for book_genre in recommended_genres[:3]
        ]
    else:
        searches = ["popular books"]

    try:
        for search in searches:
            params = {
                "q": search,
                "limit": 18,
                "fields": "key,title,author_name,subject,cover_i,ratings_average,ratings_count"
            }
            print("Searching books for:", search)

            response = requests.get(
                "https://openlibrary.org/search.json",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            results = response.json().get("docs", [])

            print("Returned books:", [book.get("title") for book in results[:5]])

            for item in results:
                cover_id = item.get("cover_i")
                rating_average = item.get("ratings_average")
                ratings_count = item.get("ratings_count", 0)

                if rating_average is not None and ratings_count:
                    rating = f" {rating_average:.1f}/5 ({ratings_count} ratings)"
                else:
                    rating = "Rating unavailable"

                books.append({
                    "book_key": item.get("key", ""),
                    "your_rating": user_ratings.get(item.get("key", "")),
                    "title": item.get("title", "Unknown title"),
                    "author": ", ".join(
                        item.get("author_name", ["Unknown author"])
                    ),
                    "genre": ", ".join(item.get("subject", [])[:3])
                        or "Uncategorized",
                    "rating": rating,
                    "cover": (
                        f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
                        if cover_id else ""
                    )
                })

    except requests.RequestException:
        error = "Unable to fetch books right now. Please try again."

    return render_template(
        "index.html",
        books=books,
        query=query,
        error=error,
        user_ratings=user_ratings
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]

        if len(password) < 8:
            error = "Password must be at least 8 characters."
        else:
            password_hash = bcrypt.generate_password_hash(
                password
            ).decode("utf-8")

            connection = get_db_connection()
            cursor = connection.cursor()

            try:
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash) "
                    "VALUES (%s, %s, %s)",
                    (username, email, password_hash)
                )
                connection.commit()

                user_id = cursor.lastrowid
                session["user_id"] = user_id
                session["username"] = username

                return redirect("/")

            except Exception as e:
                connection.rollback()
                print("Registration error:", repr(e))

                if getattr(e, "errno", None) == 1062:
                    error = "Username or email already exists. Please log in."
                else:
                    error = "Registration failed. Please try again."

            finally:
                cursor.close()
                connection.close()

    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            cursor.execute(
                "SELECT * FROM users WHERE username = %s OR email = %s",
                (username, username)
            )
            user = cursor.fetchone()

            if user and bcrypt.check_password_hash(
               user["password_hash"], password
):
               session["user_id"] = user["user_id"]
               session["username"] = user["username"]
               return redirect(url_for("home"))

            error = "Invalid username/email or password."

        finally:
            cursor.close()
            connection.close()

    return render_template("login.html", error=error)


@app.route("/delete-account", methods=["GET", "POST"])
def delete_account():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        user_id = session["user_id"]
        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "DELETE FROM ratings WHERE user_id = %s",
                (user_id,)
            )
            cursor.execute(
                "DELETE FROM users WHERE user_id = %s",
                (user_id,)
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

        session.clear()
        return redirect("/")

    return render_template("delete_account.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/rate", methods=["POST"])
def rate_book():
    if "user_id" not in session:
        return redirect(url_for("login"))

    book_key = request.form.get("book_key", "")
    book_title = request.form.get("book_title", "")
    rating = request.form.get("rating", type=int)

    if not book_key or not book_title or rating not in range(1, 6):
        return redirect(url_for("home"))

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO ratings (user_id, book_key, book_title, rating)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                rating = VALUES(rating),
                book_title = VALUES(book_title)
            """,
            (session["user_id"], book_key, book_title, rating)
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()

        genre = request.form.get("genre", "").strip()

        session["rating_message"] = "⭐ Rating saved successfully!"
        return redirect(url_for("home", genre=genre) + "#books")


if __name__ == "__main__":
    app.run(debug=True)
