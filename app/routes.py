import json
import os
from flask import Blueprint, render_template, request, redirect, url_for, session
from datetime import datetime

main = Blueprint('main', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, 'data')


def load_menu():
    with open(os.path.join(DATA_PATH, 'menu.json'), encoding='utf-8') as f:
        return json.load(f)


def load_tavoli():
    with open(os.path.join(DATA_PATH, 'tavoli.json'), encoding='utf-8') as f:
        return json.load(f)


def save_tavoli(data):
    with open(os.path.join(DATA_PATH, 'tavoli.json'), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


users = {
    "menu": "menu123",
    "cucina": "cucina123",
    "cassa": "cassa123"
}


@main.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        area = request.form.get("area")
        password = request.form.get("password")
        if area in users and users[area] == password:
            session["area"] = area
            return redirect(url_for(f"main.{area}"))
        return render_template("login.html", error="Credenziali errate")
    return render_template("login.html")


@main.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@main.route("/menu", methods=["GET", "POST"])
def menu():
    if session.get("area") != "menu" and session.get("area") != "cassa":
        return redirect(url_for("main.login"))

    menu_data = load_menu()

    if request.method == "POST":
        tavolo_id = int(request.form.get("tavolo"))
        messaggio = request.form.get("messaggio")
        ordine_nuovo = []

        for categoria, prodotti in menu_data.items():
            for i, prodotto in enumerate(prodotti):
                key = f"quantita_{categoria}_{i}"
                quantita = int(request.form.get(key, 0))
                if quantita > 0:
                    ordine_nuovo.append({
                        "categoria": categoria,
                        "prodotto": prodotto["nome"],
                        "quantita": quantita,
                        "prezzo_unitario": prodotto["prezzo"],
                        "prezzo_totale": round(prodotto["prezzo"] * quantita, 2)
                    })

        tavoli = load_tavoli()
        for tavolo in tavoli:
            if tavolo["id"] == tavolo_id:
                ordine_attuale = tavolo.get("ordine", [])
                for nuovo in ordine_nuovo:
                    trovato = False
                    for esistente in ordine_attuale:
                        if nuovo["prodotto"] == esistente["prodotto"] and nuovo["categoria"] == esistente["categoria"]:
                            esistente["quantita"] += nuovo["quantita"]
                            esistente["prezzo_totale"] = round(esistente["quantita"] * esistente["prezzo_unitario"], 2)
                            trovato = True
                            break
                    if not trovato:
                        ordine_attuale.append(nuovo)
                tavolo["ordine"] = ordine_attuale
                tavolo["messaggio"] = messaggio
                tavolo["stato"] = "ordinando"
                tavolo["ultimo_ordine"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                session["conferma_ordine"] = tavolo["ultimo_ordine"]
                break

        save_tavoli(tavoli)
        return redirect(url_for("main.menu"))

    return render_template("menu.html", menu=menu_data)


@main.route("/annulla_ordine_menu", methods=["POST"])
def annulla_ordine_menu():
    if session.get("area") != "menu" and session.get("area") != "cassa":
        return redirect(url_for("main.login"))

    tavolo_id = int(request.form.get("tavolo"))
    tavoli = load_tavoli()

    for tavolo in tavoli:
        if tavolo["id"] == tavolo_id:
            tavolo["ordine"] = []
            tavolo["messaggio"] = ""
            tavolo["stato"] = "vuoto"
            break

    save_tavoli(tavoli)
    return redirect(url_for("main.menu"))


@main.route("/cucina")
def cucina():
    if session.get("area") != "cucina":
        return redirect(url_for("main.login"))

    tavoli = load_tavoli()
    ordinazioni = sorted(
        [t for t in tavoli if t["stato"] == "ordinando"],
        key=lambda t: t.get("ultimo_ordine", "") or "0000-00-00 00:00:00",
        reverse=True
    )
    return render_template("cucina.html", ordinazioni=ordinazioni)


@main.route("/chiudi_tavolo", methods=["POST"])
def chiudi_tavolo():
    if session.get("area") != "cucina":
        return redirect(url_for("main.login"))

    tavolo_id = int(request.form.get("tavolo_id"))
    tavoli = load_tavoli()
    storico_path = os.path.join(DATA_PATH, "storico.json")
    if os.path.exists(storico_path):
        with open(storico_path, encoding="utf-8") as f:
            storico = json.load(f)
    else:
        storico = []

    for tavolo in tavoli:
        if tavolo["id"] == tavolo_id and tavolo["ordine"]:
            storico.append({
                "tavolo": tavolo["nome"],
                "ordine": tavolo["ordine"],
                "messaggio": tavolo.get("messaggio", ""),
                "orario": tavolo.get("ultimo_ordine", "-"),
                "totale": round(sum(item["prezzo_totale"] for item in tavolo["ordine"]), 2),
                "tipo": "servito"
            })
            tavolo["stato"] = "servito"
            tavolo["messaggio"] = ""
            break

    save_tavoli(tavoli)

    with open(storico_path, "w", encoding="utf-8") as f:
        json.dump(storico, f, indent=4, ensure_ascii=False)

    return redirect(url_for("main.cucina"))


@main.route("/stampa_conto", methods=["POST"])
def stampa_conto():
    if session.get("area") not in ["cassa", "cucina"]:
        return redirect(url_for("main.login"))

    tavolo_id = int(request.form.get("tavolo_id"))
    tavoli = load_tavoli()
    for tavolo in tavoli:
        if tavolo["id"] == tavolo_id and tavolo["ordine"]:
            return render_template("stampa.html", tavolo=tavolo)
    return redirect(url_for("main.cassa"))


@main.route("/cassa")
def cassa():
    if session.get("area") != "cassa":
        return redirect(url_for("main.login"))

    tavoli = load_tavoli()
    tavoli = sorted(tavoli, key=lambda t: t.get("ultimo_ordine", "") or "0000-00-00 00:00:00", reverse=True)
    return render_template("cassa.html", tavoli=tavoli)


@main.route("/chiudi_definitivo", methods=["POST"])
def chiudi_definitivo():
    if session.get("area") != "cassa":
        return redirect(url_for("main.login"))

    tavolo_id = int(request.form.get("tavolo_id"))
    tavoli = load_tavoli()

    for tavolo in tavoli:
        if tavolo["id"] == tavolo_id and tavolo["stato"] == "servito":
            tavolo["stato"] = "vuoto"
            tavolo["ordine"] = []
            break

    save_tavoli(tavoli)
    return redirect(url_for("main.cassa"))


@main.route("/modifica_comanda", methods=["POST"])
def modifica_comanda():
    if session.get("area") != "cassa":
        return redirect(url_for("main.login"))

    tavolo_id = int(request.form.get("tavolo_id"))
    items_count = int(request.form.get("items_count"))

    tavoli = load_tavoli()

    for tavolo in tavoli:
        if tavolo["id"] == tavolo_id:
            nuovo_ordine = []
            for i in range(items_count):
                quantita = int(request.form.get(f"quantita_{i}", 0))
                if quantita > 0:
                    nuovo_ordine.append({
                        "categoria": request.form.get(f"categoria_{i}"),
                        "prodotto": request.form.get(f"prodotto_{i}"),
                        "quantita": quantita,
                        "prezzo_unitario": float(request.form.get(f"prezzo_{i}")),
                        "prezzo_totale": round(float(request.form.get(f"prezzo_{i}")) * quantita, 2)
                    })
            tavolo["ordine"] = nuovo_ordine
            break

    save_tavoli(tavoli)
    return redirect(url_for("main.cassa"))


@main.route("/annulla_tavolo", methods=["POST"])
def annulla_tavolo():
    if session.get("area") != "cassa":
        return redirect(url_for("main.login"))

    tavolo_id = int(request.form.get("tavolo_id"))
    tavoli = load_tavoli()

    storico_path = os.path.join(DATA_PATH, "storico.json")
    if os.path.exists(storico_path):
        with open(storico_path, encoding="utf-8") as f:
            storico = json.load(f)
    else:
        storico = []

    for tavolo in tavoli:
        if tavolo["id"] == tavolo_id:
            if tavolo["ordine"]:
                storico.append({
                    "tavolo": tavolo["nome"],
                    "ordine": tavolo["ordine"],
                    "messaggio": tavolo.get("messaggio", ""),
                    "orario": tavolo.get("ultimo_ordine", "-"),
                    "totale": round(sum(item["prezzo_totale"] for item in tavolo["ordine"]), 2),
                    "tipo": "annullato"
                })
            tavolo["ordine"] = []
            tavolo["messaggio"] = ""
            tavolo["stato"] = "vuoto"
            break

    save_tavoli(tavoli)

    with open(storico_path, "w", encoding="utf-8") as f:
        json.dump(storico, f, indent=4, ensure_ascii=False)

    return redirect(url_for("main.cassa"))


@main.route("/storico")
def storico():
    if session.get("area") != "cassa":
        return redirect(url_for("main.login"))

    storico_path = os.path.join(DATA_PATH, "storico.json")
    if os.path.exists(storico_path):
        with open(storico_path, encoding="utf-8") as f:
            storico = json.load(f)
    else:
        storico = []

    return render_template("storico.html", storico=storico)
