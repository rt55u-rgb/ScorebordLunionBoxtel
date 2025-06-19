from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from flask import jsonify
import click
import uuid

app = Flask(__name__)
app.secret_key = 'BestuurLunionBoxtel1840'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

class User(db.Model):
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True)
    #sessie relatie
    sessions = relationship('UserSession', back_populates='user', cascade='all, delete-orphan')


class UserSession(db.Model): 
    id = Column(Integer, primary_key=True)
    session_token = Column(String(64), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    user = relationship('User', back_populates='sessions')

class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    naam = db.Column(db.String(150), nullable=False)
    p1 = db.Column(db.Integer)
    p2 = db.Column(db.Integer)
    p3 = db.Column(db.Integer)
    serie = db.Column(db.Integer)
    subtotaal = db.Column(db.Integer)
    totaal = db.Column(db.Integer)
    

@app.cli.command("init-db")
def init_db():
    db.create_all()
    click.echo("Database en tabellen succesvol aangemaakt.")

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('scores'))
    return redirect(url_for('login'))

@app.route('/wedstrijdleiding', methods=['GET', 'POST'])
def wedstrijdleiding():
    vorige_competitie = session.get('competitie', None)

    if request.method == 'POST':
        nieuwe_competitie = request.form.get('competitie')

        if nieuwe_competitie:
            # Als de competitie verandert, verwijder alle scores
            if vorige_competitie and nieuwe_competitie != vorige_competitie:
                db.session.query(Score).delete()  # Verwijder alle scores uit database
                db.session.commit()

            session['competitie'] = nieuwe_competitie
            session.modified = True
            return redirect(url_for('wedstrijdleiding'))

    huidige_competitie = session.get('competitie', '3')  # default
    return render_template('wedstrijdleiding.html', geselecteerd=huidige_competitie)



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        naam = request.form['naam'].strip()
        klasse = request.form['klasse']
        session['klasse'] = klasse
        if naam:
            session['user'] = naam
            return redirect(url_for('scores'))
        else:
            return "Vul alsjeblieft een naam in."
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'user' in session:
        naam = session['user']
        # Verwijder scores van deze gebruiker
        Score.query.filter_by(naam=naam).delete()
        db.session.commit()
        # Verwijder uit session
        session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/scores', methods=['GET', 'POST'])
def scores():
    competitie = session.get('competitie', '3')  # default naar 3 pijlen
    aantal_pijlen = int(competitie)
    if 'user' not in session:
        return redirect(url_for('login'))
    naam = session['user']

    if request.method == 'POST':
        try:
            p1 = int(request.form.get('p1',0))
            
            p2 = int(request.form.get('p2',0))
            p3 = int(request.form.get('p3',0))
        except ValueError:
            return "Voer geldige nummers in voor de pijlen."

        # Bepaal de nieuwe serie
        laatste_serie = db.session.query(db.func.max(Score.serie)).filter_by(naam=naam).scalar()
        if laatste_serie is None:
            laatste_serie = 0
        nieuwe_serie = laatste_serie + 1

        # Subtotaal van deze serie
        if competitie == 1 :
            subtotaal = p1
        else :
            subtotaal = p1 + p2 + p3
        

        # Huidige totaal berekenen (alle eerdere subtotale scores)
        eerder_subtotaal = db.session.query(db.func.sum(Score.subtotaal)).filter_by(naam=naam).scalar()
        if eerder_subtotaal is None:
            eerder_subtotaal = 0

        totaal = eerder_subtotaal + subtotaal

        # Nieuwe score opslaan
        score = Score(
            naam=naam,
            p1=p1,
            p2=p2,
            p3=p3,
            serie=nieuwe_serie,
            subtotaal=subtotaal,
            totaal=totaal
        )
        db.session.add(score)
        db.session.commit()

        return redirect(url_for('scores'))

    # Laatste 10 scores van deze gebruiker tonen
    laatste_scores = Score.query.filter_by(naam=naam).order_by(Score.id.desc()).limit(10).all()
    return render_template('scores.html', scores=laatste_scores, aantal_pijlen=aantal_pijlen)

from flask import jsonify

@app.route('/api/scoreboard')
def api_scoreboard():
    aantal_pijlen = session.get('competitie', 3)
    klasse = session.get('klasse', '')
    spelers = db.session.query(
        Score.naam,
        db.func.sum(Score.subtotaal).label('totaal'),
        db.func.max(Score.id).label('laatste_id')
    ).group_by(Score.naam).order_by(db.desc('totaal')).all()

    scoreboard_data = []
    huidige_serie = 0
    for i, speler in enumerate(spelers, start=1):
        laatste_score = Score.query.get(speler.laatste_id)
        if laatste_score:
             huidige_serie = max(huidige_serie, laatste_score.serie)
    scoreboard_data.append({
        'rang': i,
        'naam': speler.naam,
        'klasse': klasse,
        'p1': laatste_score.p1 if laatste_score else 0,
        'p2': laatste_score.p2 if laatste_score else 0,
        'p3': laatste_score.p3 if laatste_score else 0,
        'subtotaal': laatste_score.subtotaal if laatste_score else 0,
        'totaal': speler.totaal or 0,
    })


    return jsonify({  
        'data': scoreboard_data,
        'aantal_pijlen': aantal_pijlen,
        'klasse': klasse,
        'huidige_serie': huidige_serie
    })


@app.route('/scoreboard')
def scoreboard():
    competitie = session.get('competitie', '3')  # default naar 3 pijlen
    aantal_pijlen = int(competitie)
    return render_template('scoreboard.html', aantal_pijlen=aantal_pijlen)

@app.route('/reset')
def reset_scores():
    # Verwijder alle scores
    db.session.query(Score).delete()
    db.session.commit()

    # Verwijder huidige sessie zodat gebruiker op /scores wordt uitgelogd
    session.pop('user', None)

    return redirect(url_for('scoreboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Zorg dat tabellen aangemaakt zijn vóór de app start
    app.run(debug=True)
