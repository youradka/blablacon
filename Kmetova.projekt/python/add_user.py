import mysql.connector
from flask import Flask, request, render_template, flash, redirect, url_for, session
import base64
from datetime import datetime

app = Flask(__name__)
app.secret_key = "nejaky_tajny_kluc"

mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="12345",
    database="rocnikovy"
)
mycursor = mydb.cursor()

# --- JEDNODUCHÉ PODSTRÁNKY ---

@app.route('/login/sk')
def login_sk():
    return render_template("login_sk.html")

@app.route('/homepage/sk')
def homepage_sk():
    return render_template("homepage_sk.html")


@app.route('/infopage/sk')
def infopage_sk():
    return render_template("infopage_sk.html")

@app.route('/signup/sk')
def signup_sk():
    return render_template("signup_sk.html")

@app.route('/homepage/en')
def homepage_en():
    return render_template("homepage_en.html")

@app.route('/gallery/en')
def galeria_en():
    return render_template("galeria_en.html")

@app.route('/forum/en')
def forum_en():
    return render_template("forum_en.html")

@app.route('/infopage/en')
def infopage_en():
    return render_template("infopage_en.html")


# --- REGISTRÁCIA A PRIHLÁSENIE ---

@app.route('/add_user', methods=["GET", "POST"])
def add_user():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        with open("static/obrazky/default.jpg", "rb") as f:
            default_data = f.read()

        try:
            sql = "INSERT INTO users (username, heslo, email, picture) VALUES (%s, %s, %s, %s)"
            values = (username, password, email, default_data)
            mycursor.execute(sql, values)
            mydb.commit()

            flash("Registrácia prebehla úspešne!", "success")
            return redirect(url_for('forum_sk'))

        except mysql.connector.IntegrityError:
            flash("Používateľ už existuje!", "error")
            return redirect(url_for('signup_sk'))

    return render_template("signup_sk.html")

@app.route('/login_user', methods=["POST"])
def login_user():
    username = request.form.get("username")
    password = request.form.get("password")

    sql = "SELECT username FROM users WHERE (username=%s OR email=%s) AND heslo=%s"
    values = (username, username, password)

    mycursor.execute(sql, values)
    user = mycursor.fetchone()

    if user:
        session["username"] = user[0]
        return redirect(url_for('homepage_sk'))
    else:
        return render_template("login_sk.html") 

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("Úspešne si sa odhlásila.", "success")
    return redirect(url_for('forum_sk'))

@app.context_processor
def inject_user():
    profile_pic = None
    logged_in = False

    if "username" in session:
        logged_in = True
        sql = "SELECT picture FROM users WHERE username=%s"
        mycursor.execute(sql, (session["username"],))
        user_data = mycursor.fetchone()

        if user_data and user_data[0]:
            profile_pic = base64.b64encode(user_data[0]).decode("utf-8")

    return dict(
        logged_in=logged_in,
        profile_pic=profile_pic
    )


# --- ÚPRAVA PROFILU ---

@app.route('/editor/sk')
def editor_sk():
    if "username" not in session:
        flash("Pre úpravu profilu sa musíš prihlásiť.", "error")
        return redirect(url_for('login_sk'))
        
    return render_template("editor_sk.html")

@app.route('/update_profile_pic', methods=["POST"])
def update_profile_pic():
    if "username" not in session:
        return redirect(url_for('login_sk'))

    file = request.files.get("profile-pic")

    if file and file.filename != '':
        file_data = file.read()
        sql = "UPDATE users SET picture = %s WHERE username = %s"
        values = (file_data, session["username"])
        
        mycursor.execute(sql, values)
        mydb.commit()

        flash("Profilová fotka bola úspešne zmenená!", "success")
    else:
        flash("Nevybrala si žiadny súbor.", "error")

    return redirect(url_for('editor_sk'))


# --- FÓRUM (PRÍSPEVKY A KOMENTÁRE) ---

@app.route('/forum/sk')
def forum_sk():
    # Vytiahneme všetky príspevky z databázy (najnovšie prvé)
    mycursor.execute("SELECT idposty, nazov, obsah, plikes, pdatum, users_username FROM posty ORDER BY pdatum DESC")
    posts_data = mycursor.fetchall()
    
    posts = []
    for p in posts_data:
        post = {
            'idposty': p[0],
            'nazov': p[1],
            'obsah': p[2],
            'plikes': p[3],
            'pdatum': p[4],
            'autor': p[5],
            'komentare': []
        }
        
        # Vytiahneme komentáre priradené k tomuto príspevku
        sql_komenty = "SELECT users_username, kobsah, kdatum FROM komenty WHERE posty_idposty = %s ORDER BY kdatum ASC"
        mycursor.execute(sql_komenty, (post['idposty'],))
        komenty_data = mycursor.fetchall()
        
        for k in komenty_data:
            post['komentare'].append({
                'autor': k[0],
                'obsah': k[1],
                'datum': k[2]
            })
            
        posts.append(post)

    return render_template("forum_sk.html", posts=posts)


@app.route('/pridaj_prispevok', methods=["POST"])
def pridaj_prispevok():
    if "username" not in session:
        flash("Pre pridanie príspevku sa musíš prihlásiť.", "error")
        return redirect(url_for('login_sk'))

    nazov = request.form.get("nazov")
    obsah = request.form.get("obsah")
    autor = session["username"]

    aktualny_cas = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    sql = "INSERT INTO posty (nazov, obsah, plikes, users_username, pdatum) VALUES (%s, %s, 0, %s, %s)"
    
    
    mycursor.execute(sql, (nazov, obsah, autor, aktualny_cas))
    mydb.commit()

    flash("Príspevok bol úspešne pridaný!", "success")
    return redirect(url_for('forum_sk'))


@app.route('/pridaj_komentar/<int:idposty>', methods=["POST"])
def pridaj_komentar(idposty):
    if "username" not in session:
        flash("Pre pridanie komentára sa musíš prihlásiť.", "error")
        return redirect(url_for('login_sk'))

    kobsah = request.form.get("kobsah")
    autor = session["username"]

    aktualny_cas = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # ZMENA: Do príkazu INSERT sme pridali stĺpec 'kdatum' a ďalšie '%s'
    sql = "INSERT INTO komenty (kobsah, posty_idposty, users_username, kdatum) VALUES (%s, %s, %s, %s)"
    
    # ZMENA: Posielame 'aktualny_cas' ako štvrtú hodnotu
    mycursor.execute(sql, (kobsah, idposty, autor, aktualny_cas))
    mydb.commit()

    return redirect(url_for('forum_sk'))

@app.route('/vymaz_prispevok/<int:idposty>', methods=["POST"])
def vymaz_prispevok(idposty):
    # Overíme, či je používateľ prihlásený
    if "username" not in session:
        flash("Na vymazanie príspevku sa musíš prihlásiť.", "error")
        return redirect(url_for('login_sk'))

    aktualny_pouzivatel = session["username"]

    # Zistíme, kto je autorom tohto príspevku
    mycursor.execute("SELECT users_username FROM posty WHERE idposty = %s", (idposty,))
    post = mycursor.fetchone()

    # Ak príspevok existuje a prihlásený používateľ je jeho autorom
    if post and post[0] == aktualny_pouzivatel:
        # NAJPRV vymažeme všetky komentáre, ktoré patria k tomuto príspevku
        mycursor.execute("DELETE FROM komenty WHERE posty_idposty = %s", (idposty,))
        
        # POTOM vymažeme samotný príspevok
        mycursor.execute("DELETE FROM posty WHERE idposty = %s", (idposty,))
        
        mydb.commit()
        flash("Príspevok bol úspešne vymazaný.", "success")
    else:
        # Ak sa niekto snaží vymazať cudzí príspevok
        flash("Tento príspevok nemôžeš vymazať, pretože nie si jeho autorom.", "error")

    # Po úspešnom vymazaní (alebo chybe) obnovíme stránku fóra
    return redirect(url_for('forum_sk'))

@app.route('/galeria/sk')
def galeria_sk():
    # Vytiahneme všetky obrázky z galérie
    mycursor.execute("SELECT idgaleria, nazov, popis, obrazok, fandom, users_username FROM galeria")
    galeria_data = mycursor.fetchall()

    fandomy_dict = {}
    
    for row in galeria_data:
        idgaleria = row[0]
        nazov = row[1]
        popis = row[2]
        obrazok_blob = row[3]
        fandom = row[4]
        autor = row[5]

        # Konverzia BLOBu na Base64 string pre HTML (ak obrázok existuje)
        obrazok_base64 = None
        if obrazok_blob:
            obrazok_base64 = base64.b64encode(obrazok_blob).decode('utf-8')

        # Vytvoríme štruktúru jedného príspevku do galérie
        polozka = {
            'idgaleria': idgaleria,
            'nazov': nazov,
            'popis': popis,
            'obrazok': obrazok_base64,
            'autor': autor
        }

        # Zoskupovanie do slovníka podľa fandomu
        # Ak fandom ešte nie je v slovníku, vytvoríme preň prázdny list
        if fandom not in fandomy_dict:
            fandomy_dict[fandom] = []
            
        # Pridáme položku do správneho "priečinka" (fandomu)
        fandomy_dict[fandom].append(polozka)

    # Do šablóny pošleme slovník, kde kľúče sú názvy fandomov a hodnoty sú zoznamy obrázkov
    return render_template("galeria_sk.html", fandomy=fandomy_dict)


@app.route('/pridaj_do_galerie', methods=["POST"])
def pridaj_do_galerie():
    if "username" not in session:
        flash("Pre pridanie do galérie sa musíš prihlásiť.", "error")
        return redirect(url_for('login_sk'))

    nazov = request.form.get("nazov")
    popis = request.form.get("popis")
    fandom = request.form.get("fandom")
    autor = session["username"]
    
    file = request.files.get("fotka")

    if file and file.filename != '':
        obrazok_data = file.read()

        sql = "INSERT INTO galeria (nazov, popis, obrazok, fandom, users_username) VALUES (%s, %s, %s, %s, %s)"
        mycursor.execute(sql, (nazov, popis, obrazok_data, fandom, autor))
        mydb.commit()

        flash("Obrázok bol úspešne pridaný do galérie!", "success")
    else:
        flash("Musíš vybrať obrázok.", "error")

    return redirect(url_for('galeria_sk'))

@app.route('/vymaz_z_galerie/<int:idgaleria>', methods=["POST"])
def vymaz_z_galerie(idgaleria):
    if "username" not in session:
        flash("Na vymazanie obrázka sa musíš prihlásiť.", "error")
        return redirect(url_for('login_sk'))

    aktualny_pouzivatel = session["username"]

    # Najprv zistíme, kto obrázok pridal
    mycursor.execute("SELECT users_username FROM galeria WHERE idgaleria = %s", (idgaleria,))
    foto = mycursor.fetchone()

    # Ak fotka existuje a prihlásený používateľ je jej autorom
    if foto and foto[0] == aktualny_pouzivatel:
        mycursor.execute("DELETE FROM galeria WHERE idgaleria = %s", (idgaleria,))
        mydb.commit()
        flash("Obrázok bol z galérie úspešne vymazaný.", "success")
    else:
        flash("Tento obrázok nemôžeš vymazať, pretože nie si jeho autorom.", "error")

    return redirect(url_for('galeria_sk'))

@app.route('/hlasuj/<int:idposty>/<akcia>', methods=["POST"])
def hlasuj(idposty, akcia):
    # 1. KONTROLA: Je používateľ vôbec prihlásený?
    if "username" not in session:
        flash("Pre hlasovanie sa musíš prihlásiť.", "error")
        return redirect(url_for('forum_sk'))

    aktualny_pouzivatel = session["username"]

    # 2. KONTROLA: Snaží sa používateľ daň lajk vlastnému postu?
    # Vytiahneme autora príspevku z databázy
    mycursor.execute("SELECT users_username FROM posty WHERE idposty = %s", (idposty,))
    post = mycursor.fetchone()
    
    if post and post[0] == aktualny_pouzivatel:
        # Ak sa meno autora zhoduje s prihláseným, vypíšeme chybu a nepustíme ho ďalej
        flash("Nemôžeš hlasovať za svoj vlastný príspevok!", "error")
        return redirect(url_for('forum_sk'))

    # 3. KONTROLA: Hlasoval už tento človek za tento príspevok v minulosti?
    # Pozrieme sa do našej novej pamäťovej tabuľky 'hlasovania'
    sql_kontrola = "SELECT id FROM hlasovania WHERE posty_idposty = %s AND users_username = %s"
    mycursor.execute(sql_kontrola, (idposty, aktualny_pouzivatel))
    uz_hlasoval = mycursor.fetchone()

    if uz_hlasoval:
        # Ak tam už o ňom máme záznam, stopneme ho
        flash("Za tento príspevok si už hlasoval(a).", "error")
        return redirect(url_for('forum_sk'))

    # 4. SAMOTNÉ HLASOVANIE: Ak prešiel kontrolami, spracujeme hlas
    if akcia == "up":
        sql_update = "UPDATE posty SET plikes = plikes + 1 WHERE idposty = %s"
    elif akcia == "down":
        sql_update = "UPDATE posty SET plikes = plikes - 1 WHERE idposty = %s"
    else:
        return redirect(url_for('forum_sk'))

    # 5. ZÁPIS STOPY: Zapíšeme do tabuľky hlasovania, že tento človek už klikol
    sql_insert = "INSERT INTO hlasovania (posty_idposty, users_username) VALUES (%s, %s)"
    
    # Vykonáme oba príkazy naraz a uložíme (commit)
    mycursor.execute(sql_update, (idposty,))
    mycursor.execute(sql_insert, (idposty, aktualny_pouzivatel))
    mydb.commit()

    # Všetko prebehlo v poriadku, obnovíme fórum
    return redirect(url_for('forum_sk'))

# --- SPUSTENIE SERVERA (MUSÍ BYŤ ÚPLNE NA KONCI) ---
if __name__ == "__main__":
    app.run(debug=True)