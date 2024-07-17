import pymysql
from flask import Flask, request, jsonify, render_template
from flask_mysqldb import MySQL

app = Flask(__name__)

app.config['MYSQL_HOST'] = 'sql.freedb.tech'
app.config['MYSQL_PORT'] = 3306
app.config['MYSQL_USER'] = 'reacted'
app.config['MYSQL_PASSWORD'] = 'reacted'
app.config['MYSQL_DB'] = 'freedb_library'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

        

mysql = MySQL(app)
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')
@app.route('/cupboards', methods=['GET'])
def fetch_cupboards():
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, name FROM cupboard")
        cupboards = cursor.fetchall()
        cursor.close()
        return jsonify(cupboards)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/rows', methods=['GET'])
def fetch_rows():
    cupboard_id = request.args.get('cupboardId')
    if not cupboard_id:
        return jsonify([])

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT row_number_inside_cupboard as id, category as name FROM roww WHERE cupboard_id = %s", (cupboard_id,))
        rows = cursor.fetchall()
        cursor.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/addbook', methods=['POST'])
def add_book():
    data = request.json
    isbn = data.get('isbn')
    title = data.get('title')
    author = data.get('author')
    publisher = data.get('publisher')
    rowid = int(data.get('rowid'))  # Assuming rowid is an integer
    cupboardid = int(data.get('cupboardid'))  # Assuming cupboardid is an integer
    barcode = data.get('barcode')
    if not (title and cupboardid and rowid):
        return jsonify({'error': 'Incomplete data provided'}), 400

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM books WHERE barcode = %s", (barcode,))
        existing_book = cursor.fetchone()
        if existing_book:
            cursor.close()
            return jsonify({'error': 'Barcode already exists for another book. Consider editing the existing book or choose a different barcode.'}), 400

        cursor.execute("INSERT INTO books (isbn, title, author, publisher, destination_row, cupboard_id, added_manually, copies_available, barcode) VALUES (%s, %s, %s, %s, %s, %s, 1, 1, %s)", (isbn, title, author, publisher, rowid, cupboardid, barcode))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Book added successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/book/<int:book_id>', methods=['GET'])
def get_book(book_id):
    try:
        cursor = mysql.connection.cursor()
        cursor.execute('''SELECT 
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
                                books.book_id = %s;''', (book_id,))
        book = cursor.fetchone()
        cursor.close()
        return jsonify({'book': book}), 200 if book else 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/search', methods=['GET'])
def search_books():
    query = request.args.get('query')
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
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
                        """, ('%' + query + '%', '%' + query + '%', '%' + query + '%'))
        books = cursor.fetchall()
        cursor.close()
        return jsonify({'books': books}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/add_duplicate', methods=['POST'])
def add_duplicate_book():
    data = request.json
    book_id = data.get('bookID')
    barcode = data.get('barcode')

    if not (book_id and barcode):
        return jsonify({'error': 'Incomplete data provided'}), 400

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM books WHERE book_id = %s", (book_id,))
        book = cursor.fetchone()
        if not book:
            cursor.close()
            return jsonify({'error': 'Book not found'}), 404
        book_title = book['title']

        cursor.execute("SELECT * FROM books WHERE barcode = %s", (barcode,))
        existing_book = cursor.fetchone()
        if existing_book:
            cursor.close()
            return jsonify({'error': 'Barcode already exists for another book. Consider editing the existing book or choose a different barcode.'}), 400

        cursor.execute("""
                        INSERT INTO books (isbn, title, author, publisher, added_manually, cupboard_id, destination_row, category_name, copies_available, barcode)
                        SELECT isbn, title, author, publisher, added_manually, cupboard_id, destination_row, category_name, copies_available, %s
                        FROM books
                        WHERE book_id = %s
                        """, (barcode, book_id))
        cursor.execute("UPDATE books set copies_available=copies_available+1 where title=%s", (book_title,))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Duplicate book added successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/update', methods=['POST'])
def update_book():
    data = request.json
    book_id = data.get('bookID')
    destinationcupboard = data.get('destinationcupboard')
    destinationrow = data.get('destinationrow')
    barcode = data.get('barcode')

    if not (book_id and destinationcupboard and destinationrow and barcode):
        return jsonify({'error': 'Incomplete data provided'}), 400

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM books WHERE barcode = %s AND book_id != %s", (barcode, book_id))
        existing_book = cursor.fetchone()
        if existing_book:
            cursor.close()
            return jsonify({'error': 'Barcode already exists for another book. Consider editing the existing book or choose a different barcode.'}), 400
        cursor.execute("UPDATE books SET cupboard_id = %s, destination_row = (SELECT id from roww where row_number_inside_cupboard = %s and cupboard_id = %s), barcode = %s WHERE book_id = %s", (destinationcupboard, destinationrow, destinationcupboard, barcode, book_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Book updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
