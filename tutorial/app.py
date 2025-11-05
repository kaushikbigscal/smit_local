from flask import Flask, redirect,render_template,url_for,request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
# Configure PostgreSQL database URI
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:123@localhost/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

db = SQLAlchemy(app)

class Item(db.Model):
    id = db.Column(db.Integer,primary_key=True)
    name = db.Column(db.String(100), nullable = False)

    def __repr__(self):
        return f'<Item{self.name}>'

with app.app_context():
    db.create_all()

@app.route('/')

def home():
    items = Item.query.all()
    return render_template('index.html',items=items)


@app.route('/add', methods=['POST'])
def add():
    item_name = request.form.get('item')
    if item_name:
        new_item = Item(name=item_name)
        db.session.add(new_item)
        db.session.commit()
        db.session.rollback()
    return redirect(url_for('home'))

@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
def edit(item_id):
    item = Item.query.get_or_404(item_id)
    if request.method == 'POST':
        item.name = request.form.get('item')
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('edit.html', item=item)

@app.route('/delete/<int:item_id>')
def delete(item_id):
    item = Item.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('home'))



if __name__ == '__main__':
    app.run(debug=True)