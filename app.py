import pymysql
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

HOST = 'srv1273.hstgr.io'
PORT = 3306
DATABASE = 'u131501769_library'
USER = 'muzu04994'
PASSWORD = 'Shanid@786'

def connect_to_database():
    return pymysql.connect(host=HOST, port=PORT, user=USER, password=PASSWORD, database=DATABASE, cursorclass=pymysql.cursors.DictCursor)
def get_cupboards():
    connection = connect_to_database()
    try:
        with connection.cursor() as cursor:
            sql = "SELECT id, name FROM cupboard"
            cursor.execute(sql)
            result = cursor.fetchall()
    finally:
        connection.close()
    return result

# Fetch rows for a given cupboard from database
def get_rows(cupboard_id):
    connection = connect_to_database()
    try:
        with connection.cursor() as cursor:
            sql = "SELECT row_number_inside_cupboard as id, category as name FROM roww WHERE cupboard_id = %s"
            cursor.execute(sql, (cupboard_id,))
            result = cursor.fetchall()
    finally:
        connection.close()
    return result

@app.route('/cupboards', methods=['GET'])
def fetch_cupboards():
    cupboards = get_cupboards()
    return jsonify(cupboards)

@app.route('/rows', methods=['GET'])
def fetch_rows():
    cupboard_id = request.args.get('cupboardId')
    if cupboard_id:
        rows = get_rows(cupboard_id)
        return jsonify(rows)
    else:
        return jsonify([])
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/book/<int:book_id>', methods=['GET'])
def get_book(book_id):
    # Connect to the database
    connection = connect_to_database()
    try:
        with connection.cursor() as cursor:
            # Fetch book details by ID
            sql = '''SELECT 
    books.*, 
    roww.row_number_inside_cupboard, 
    roww.category AS rowname, 
    cupboard.name AS cupname 
FROM 
    books 
JOIN 
    roww ON books.destination_row = roww.id 
JOIN 
    cupboard ON books.cupboard_id = cupboard.id 
WHERE 
    books.book_id = %s;
'''
            cursor.execute(sql, (book_id,))
            book = cursor.fetchone()
            return jsonify({'book': book}), 200 if book else 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

@app.route('/search', methods=['GET'])
def search_books():
    query = request.args.get('query')
    connection = connect_to_database()
    try:
        with connection.cursor() as cursor:
            sql_query = """
                SELECT 
    books.*, 
    roww.category AS roww_category,
    roww.row_number_inside_cupboard,
    cupboard.id AS cupboard_id,
    cupboard.name AS cupname,
    roww.category AS rowname,
    CASE
        WHEN books.barcode IS NOT NULL THEN 'assigned'
        ELSE 'not_assigned'
    END AS barcode_status
FROM 
    books
LEFT JOIN 
    roww ON books.destination_row = roww.id
LEFT JOIN 
    cupboard ON roww.cupboard_id = cupboard.id
WHERE 
    books.isbn LIKE %s 
    OR books.title LIKE %s 
    OR books.barcode LIKE %s 
ORDER BY 
    books.title;
"""
            cursor.execute(sql_query, ('%' + query + '%', '%' + query + '%', '%' + query + '%'))
            books = cursor.fetchall()
            return jsonify({'books': books}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

@app.route('/addbook', methods=['POST'])
def add_book():
    data = request.json
    isbn = data.get('isbn')
    title = data.get('title')
    author = data.get('author')
    publisher =data.get('publisher')
    rowid = int(data.get('rowid'))  # Assuming rowid is an integer
    cupboardid = int(data.get('cupboardid'))  # Assuming cupboardid is an integer
    barcode=data.get('barcode')
    if not ( title and cupboardid and rowid):
        return jsonify({'error': 'Incomplete data provided'}), 400

    connection = connect_to_database()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM books WHERE barcode = %s ", (barcode))
            existing_book = cursor.fetchone()
            if existing_book:
                return jsonify({
                    'error': 'Barcode already exists for another book. Consider editing the existing book or choose a different barcode.'}), 400

            # Insert new book into the database
            sql = '''INSERT INTO books (
    isbn, 
    title, 
    author, 
    publisher, 
    destination_row, 
    cupboard_id, 
    added_manually, 
    copies_available, 
    barcode
) 
VALUES (
    %s,                          -- Placeholder 1 (isbn)
    %s,                          -- Placeholder 2 (title)
    %s,                          -- Placeholder 3 (author)
    %s,                          -- Placeholder 4 (publisher)
    (SELECT id FROM roww WHERE row_number_inside_cupboard = %s AND cupboard_id = %s),  -- Subquery as Placeholder 5 and 6
    %s,
    1,                           -- Static value 1 (added_manually)
    1,                           -- Static value 1 (copies_available)
    %s                           -- Placeholder 7 (barcode)
)
'''
            cursor.execute(sql, (isbn, title, author, publisher, rowid,cupboardid, cupboardid, barcode))
            connection.commit()
            return jsonify({'message': ' book added successfully'}), 200
    except pymysql.Error as e:
            print(f"Error code {e.args[0]}: {e}")
            return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

@app.route('/add_duplicate', methods=['POST'])
def add_duplicate_book():
    data = request.json
    book_id = data.get('bookID')
    barcode = data.get('barcode')

    if not (book_id and barcode):
        return jsonify({'error': 'Incomplete data provided'}), 400

    connection = connect_to_database()
    try:
        with connection.cursor() as cursor:
            # Fetch the book details
            cursor.execute("SELECT * FROM books WHERE book_id = %s", (book_id,))
            book = cursor.fetchone()
            if not book:
                return jsonify({'error': 'Book not found'}), 404
            book_title = book['title']
            print("Book Title:", book_title)
            # Insert a duplicate of the book with a new barcode
            cursor.execute("SELECT * FROM books WHERE barcode = %s ", (barcode))
            existing_book = cursor.fetchone()
            if existing_book:
                return jsonify({
                                   'error': 'Barcode already exists for another book. Consider editing the existing book or choose a different barcode.'}), 400

            cursor.execute("""
                INSERT INTO books (isbn, title, author, publisher, added_manually, cupboard_id, destination_row, category_name, copies_available, barcode)
                SELECT isbn, title, author, publisher, added_manually, cupboard_id, destination_row, category_name, copies_available, %s
                FROM books
                WHERE book_id = %s
            """, (barcode, book_id))
            cursor.execute("""
                            UPDATE books set copies_available=copies_available+1 where title=%s
                        """, (book_title))
            connection.commit()
            return jsonify({'message': 'Duplicate book added successfully'}), 200
    except pymysql.Error as e:
            print(f"Error code {e.args[0]}: {e}")
            return jsonify({'error': str(e)}), 500

    finally:
        connection.close()

@app.route('/update', methods=['POST'])
def update_book():
    data = request.json
    book_id = data.get('bookID')
    destinationcupboard = data.get('destinationcupboard')
    destinationrow = data.get('destinationrow')
    barcode = data.get('barcode')

    if not (book_id and destinationcupboard and destinationrow and barcode):
        return jsonify({'error': 'Incomplete data provided'}), 400

    connection = connect_to_database()
    try:
        with connection.cursor() as cursor:
            # Check if barcode already exists
            cursor.execute("SELECT * FROM books WHERE barcode = %s AND book_id != %s", (barcode, book_id))
            existing_book = cursor.fetchone()
            if existing_book:
                return jsonify({'error': 'Barcode already exists for another book. Consider editing the existing book or choose a different barcode.'}), 400
            sql = """
               UPDATE books
                SET cupboard_id = %s, 
                    destination_row = (SELECT id from roww where row_number_inside_cupboard = %s and cupboard_id = %s), 
                    barcode = %s
                WHERE book_id = %s
            """
            cursor.execute(sql, (destinationcupboard, destinationrow, destinationcupboard, barcode, book_id))
            connection.commit()
            return jsonify({'message': 'Book updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

if __name__ == '__main__':
    app.run(debug=True)
