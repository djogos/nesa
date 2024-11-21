import pandas as pd
from googleapiclient.discovery import build
from google.oauth2 import service_account
import os
import sys
import streamlit as st
import time

valid_users = st.secrets["users"]

# Учитавање креденцијала из Streamlit тајни
credentials_info = st.secrets["google_credentials"]

# Креирање Google Service Account Credentials објекта
creds = service_account.Credentials.from_service_account_info(
    credentials_info
)

# Постављање параметара за Google Sheets API
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = st.secrets["spreadsheet"]["sheet"]

# Креирање сервисног објекта
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

# Логика за пријаву
def login():
    st.title("Uloguj se!")

    username = st.text_input("Korisničko ime")
    password = st.text_input("Lozinka", type="password")

    if st.button("Uloguj se"):
        if username in valid_users and valid_users[username] == password:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.success(f"Dobrodošli, {username}!")
        else:
            st.error("Nevalidno korisničko ime ili lozinka.")

# Funkcija za čitanje podataka iz Google Sheet-a
def citaj_podatke():
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range='Magacin').execute()
    values = result.get('values', [])
    if not values:
        return pd.DataFrame(columns=['Id',
         'Naziv stavke',
         'Tip',
         'Cena',
         'Zalihe',
         'Status',
         'Napomene'])
    else:
        temp = pd.DataFrame(values[1:], columns=values[0])
        temp['Cena'] = temp['Cena'].apply(lambda x: x[4:].replace('.', '').replace(',', '.'))
        temp[['Cena', 'Zalihe']] = temp[['Cena', 'Zalihe']].astype(float)
        return temp

# Funkcija za upisivanje podataka u Google Sheet
def upisi_podatke(df):
    request = sheet.values().clear(spreadsheetId=SPREADSHEET_ID, range='Magacin')
    request.execute()
    vrednosti = [df.columns.tolist()] + df.values.tolist()
    body = {'values': vrednosti}
    sheet.values().update(spreadsheetId=SPREADSHEET_ID, range='Magacin',
                          valueInputOption='RAW', body=body).execute()
tipovi_proizvoda = ['drvo', 'drvo lr', 'drvo db', 'pokl tegle', 'satna', 'staklo ili ambalaža']

# Логика за приступ заштићеним садржајима
def main():
    if "logged_in" not in st.session_state or not st.session_state.logged_in:
        login()  # Ако није пријављен, позови login()
    else:
        st.write(f"Добродошли {st.session_state.username}, ово је заштићена страница!")
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.rerun()  # Поново учитај апликацију
        # Dugme za osvežavanje u sidebar-u
        # Učitavanje podataka
        df = citaj_podatke()
        if st.sidebar.button("Osveži podatke"):
            # Brisanje keša
            st.cache_data.clear()
            # Ponovno učitavanje podataka
            df = citaj_podatke()
            st.success("Podaci su osveženi!")
            
        #if st.sidebar.button("Zatvori aplikaciju"):
        #    os._exit(0)
        
        # Kreiranje tabova
        tab1, tab2, tab3, tab4 = st.tabs(["Dodaj proizvod", "Promeni stanje", "Obriši proizvod", "Prikaži stanje"])
        
        # Tab 1: Dodaj proizvod
        with tab1:
            st.header("Dodaj novi proizvod")
            with st.form("novi_proizvod"):
                naziv = st.text_input("Naziv:")
                tip = st.selectbox("Tip:", tipovi_proizvoda)
                cena = st.number_input("Cena:", min_value=0.0, step=0.01)
                zalihe = st.number_input("Zalihe:", min_value=0.0, step=0.01)
                status = 'Nepoznat'
                napomene = st.text_input("Napomene:")
                if st.form_submit_button("Dodaj"):
                    if naziv in df['Naziv stavke'].values:
                        st.error("Proizvod sa tim nazivom već postoji!")
                    else:
                        novi_proizvod = pd.DataFrame([[len(df) + 1, naziv, tip, cena, zalihe, status, napomene]], columns=df.columns)
                        df = pd.concat([df, novi_proizvod], ignore_index=True)
                        upisi_podatke(df)
                        st.success("Proizvod dodat!")
        
        # Tab 2: Promeni stanje
        with tab2:
            st.header("Promeni stanje proizvoda")
            with st.form("promeni_stanje"):
                izabrani_proizvod = st.selectbox("Izaberite proizvod:", df['Naziv stavke'])
                indeks = df[df['Naziv stavke'] == izabrani_proizvod].index[0]
        
                # Unos vrednosti za uvećanje/smanjenje
                x = st.number_input("Vrednost za promenu:", min_value=0, step=1)
        
                # Dugmad za uvećanje i smanjenje
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Uvećaj"):
                        df.loc[indeks, 'Zalihe'] += x
                        upisi_podatke(df)
                        st.success(f"Zalihe proizvoda '{izabrani_proizvod}' uvećane za {x}.")
                with col2:
                    if st.form_submit_button("Smanji"):
                        if df['Zalihe'][indeks] >= x:
                            df.loc[indeks, 'Zalihe'] -= x
                            upisi_podatke(df)
                            st.success(f"Zalihe proizvoda '{izabrani_proizvod}' smanjene za {x}.")
                        else:
                            st.error(f"Nema dovoljno zaliha proizvoda '{izabrani_proizvod}'.")
        
        # Tab 3: Obriši proizvod
        with tab3:
            st.header("Obriši proizvod")
            with st.form("obrisi_proizvod"):
                izabrani_proizvod = st.selectbox("Izaberite proizvod za brisanje:", df['Naziv stavke'])
                if st.form_submit_button("Obriši"):
                    df = df[df['Naziv stavke'] != izabrani_proizvod]
                    upisi_podatke(df)
                    st.success("Proizvod obrisan!")
        
        # Tab 4: Prikaži stanje
        with tab4:
            st.header("Stanje magacina")
        
            # Omogućavanje izmene DataFrame-a
            edited_df = st.data_editor(df)
        
            # Dugme za potvrdu promena
            if st.button("Potvrdi promene"):
                # Provera da li je DataFrame izmenjen
                if edited_df is not df:
                    st.success("Podaci su uspešno izmenjeni!")
                    # Upisivanje izmenjenog DataFrame-a u Google Sheet
                    upisi_podatke(edited_df)
                else:
                    st.warning("Niste napravili nikakve promene.")

if __name__ == "__main__":
    main()

            
