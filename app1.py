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

    with st.form("logovanje"):
        username = st.text_input("Korisničko ime")
        password = st.text_input("Lozinka", type="password")
    
        if st.form_submit_button("Uloguj se"):
            if username in valid_users and valid_users[username] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success(f"Dobrodošli, {username}!")
                st.rerun()
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
         'Pakovanje',
         'Napomene',
         'Zbir'])
    else:
        temp = pd.DataFrame(values[1:], columns=values[0])
        temp['Cena'] = temp['Cena'].fillna('0')
        temp['Cena'] = temp['Cena'].apply(lambda x: x.replace('.', '').replace(',', '.'))
        temp['Cena'] = temp['Cena'].str.extract('(-{0,1}\d+\.\d+)', expand=False).astype(float).fillna(0)
        temp['Zalihe'] = temp['Zalihe'].astype(float, errors='ignore').fillna(0)
        temp['Zbir'] = temp['Zbir'].fillna('0')
        temp['Zbir'] = temp['Zbir'].apply(lambda x: x.replace('.', '').replace(',', '.'))
        temp['Zbir'] = temp['Zbir'].str.extract('(-{0,1}\d+\.\d+)', expand=False).astype(float).fillna(0)
        return temp

# Funkcija za upisivanje podataka u Google Sheet
def upisi_podatke(df):
    request = sheet.values().clear(spreadsheetId=SPREADSHEET_ID, range='Magacin')
    request.execute()
    vrednosti = [df.columns.tolist()] + df.values.tolist()
    body = {'values': vrednosti}
    sheet.values().update(spreadsheetId=SPREADSHEET_ID, range='Magacin',
                          valueInputOption='RAW', body=body).execute()
tipovi_proizvoda = ['satna', 'ambalaža', 'drvo', 'boca', 'razno', 'staklo', 'pribor', 'oprema']


if "logged_in" not in st.session_state or not st.session_state.logged_in:
    login()  # Ако није пријављен, позови login()
else:
    if st.sidebar.button("Izloguj se"):
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
    tab4, tab2, tab1, tab3  = st.tabs(["Prikaži stanje", "Promeni stanje", "Dodaj proizvod", "Obriši proizvod"])
    
    # Tab 1: Dodaj proizvod
    with tab1:
        st.header("Dodaj novi proizvod")
        with st.form("novi_proizvod"):
            sifra = st.text_input("Id:")
            naziv = st.text_input("Naziv:")
            tip = st.selectbox("Tip:", tipovi_proizvoda)
            cena = st.number_input("Cena:", min_value=0.0, step=0.01)
            zalihe = st.number_input("Zalihe:", min_value=0.0, step=0.01)
            pakovanje = st.text_input("Pakovanje:")
            napomene = st.text_input("Napomene:")
            if st.form_submit_button("Dodaj"):
                if naziv in df['Naziv stavke'].values:
                    st.error("Proizvod sa tim nazivom već postoji!")
                elif sifra in df['Id'].values:
                    st.error("Proizvod sa tim id-jem već postoji!")
                elif sifra.strip() == "":
                        st.error("Morate popuniti polje Id:")
                elif naziv.strip() == "":
                    st.error("Morate popuniti polje Naziv:")
                else:
                    zbir = cena*zalihe
                    novi_proizvod = pd.DataFrame([[sifra, naziv, tip, cena, zalihe, pakovanje, napomene, zbir]], columns=df.columns)
                    df = pd.concat([df, novi_proizvod], ignore_index=True)
                    #st.write(df)
                    upisi_podatke(df)
                    st.success("Proizvod dodat!")
                    #st.rerun()
    
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
                    df.loc[indeks, 'Zalihe'] = float(df.loc[indeks, 'Zalihe']) + float(x)
                    df.loc[indeks, 'Zbir'] = float(df.loc[indeks, 'Cena'])*float(df.loc[indeks, 'Zalihe'])
                    upisi_podatke(df)
                    st.success(f"Zalihe proizvoda '{izabrani_proizvod}' uvećane za {x}.")
            with col2:
                if st.form_submit_button("Smanji"):
                    if float(df['Zalihe'][indeks]) >= x:
                        df.loc[indeks, 'Zalihe'] = float(df.loc[indeks, 'Zalihe']) - float(x)
                        df.loc[indeks, 'Zbir'] = float(df.loc[indeks, 'Cena'])*float(df.loc[indeks, 'Zalihe'])
                        upisi_podatke(df)
                        st.success(f"Zalihe proizvoda '{izabrani_proizvod}' smanjene za {x}.")
                    else:
                        st.error(f"Nema dovoljno zaliha proizvoda '{izabrani_proizvod}'.")
    
    # Tab 3: Obriši proizvod
    with tab3:
        st.header("Obriši proizvod")
        
        izabrani_proizvod = st.selectbox("Izaberite proizvod za brisanje:", df['Naziv stavke'])
        if st.button("Obriši"):
            df = df[df['Naziv stavke'] != izabrani_proizvod]
            upisi_podatke(df)
            st.success("Proizvod obrisan!")
            st.rerun()
    
    # Tab 4: Prikaži stanje
    with tab4:
        st.header("Stanje magacina")
    
        # Omogućavanje izmene DataFrame-a
        edited_df = st.data_editor(df)
    
        # Dugme za potvrdu promena
        if st.button("Potvrdi promene"):
            # Provera da li je DataFrame izmenjen
            if edited_df is not df:
                # Upisivanje izmenjenog DataFrame-a u Google Sheet
                edited_df['Cena'] = edited_df['Cena'].astype(float, errors='coerce').fillna(0)
                edited_df['Zalihe'] = edited_df['Zalihe'].astype(float, errors='coerce').fillna(0)
                edited_df['Zbir'] = edited_df['Cena'] * edited_df['Zalihe']
                upisi_podatke(edited_df)
                st.success("Podaci su uspešno izmenjeni!")
            else:
                st.warning("Niste napravili nikakve promene.")



            
