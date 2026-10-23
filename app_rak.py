import pandas as pd
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import io
import datetime

st.set_page_config(layout="wide", page_title="Tracker Gudang Pro")
st.title("📦 Sistem Tracker Rak Gudang")

@st.cache_data
def load_all_sheets(file_name):
    try:
        return pd.ExcelFile(file_name).sheet_names
    except Exception:
        return []

@st.cache_data
def load_rack_layout(file_name, sheet_name):
    df = pd.read_excel(file_name, sheet_name=sheet_name, header=None)
    return df.replace(np.nan, '', regex=True)

# Fungsi membuat PDF yang sudah ditambahkan Ringkasan
def generate_pdf_layout(df_layout, sbin_db, sheet_name, tot_terisi, tot_kosong, tot_material, tgl_str):
    # Tambah tinggi gambar sedikit (ditambah 2.5) untuk area teks ringkasan di atas
    fig, ax = plt.subplots(figsize=(df_layout.shape[1] * 0.6, (df_layout.shape[0] * 0.4) + 2.5))
    ax.set_xlim(0, df_layout.shape[1])
    ax.set_ylim(0, df_layout.shape[0])
    ax.invert_yaxis()
    ax.axis('off')

    # Menggambar kotak-kotak SBin
    for r in range(df_layout.shape[0]):
        for c in range(df_layout.shape[1]):
            val = str(df_layout.iat[r, c]).strip()
            if val != "" and val.upper() not in ["KANTOR", "JALAN", "PINTU", "TYPE", "RAK"]:
                is_terisi = sbin_db.get(val, False)
                warna_bg = '#90EE90' if is_terisi else '#FFFFFF'
                rect = Rectangle((c, r), 0.9, 0.9, facecolor=warna_bg, edgecolor='black', linewidth=1)
                ax.add_patch(rect)
                ax.text(c + 0.45, r + 0.45, val, ha='center', va='center', fontsize=6)
            elif val.upper() in ["KANTOR", "JALAN", "PINTU"]:
                rect = Rectangle((c, r), 0.9, 0.9, facecolor='#DDDDDD', edgecolor='none')
                ax.add_patch(rect)
                ax.text(c + 0.45, r + 0.45, val, ha='center', va='center', fontsize=7, fontweight='bold', color='gray')
                
    # Menuliskan Teks Ringkasan di atas layout
    teks_ringkasan = (
        f"Data Tanggal: {tgl_str}\n"
        f"----------------------------------\n"
        f"• SBin Terisi : {tot_terisi} SBin\n"
        f"• SBin Kosong : {tot_kosong} SBin\n"
        f"• Material di Jalan : {tot_material} Item"
    )
    # Posisikan teks ringkasan (x=0.5 tengah, y=0.95 atas)
    fig.text(0.5, 0.95, teks_ringkasan, ha='center', va='top', fontsize=12, 
             bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#ced4da"))

    # Menambahkan judul PDF (diturunkan sedikit agar tidak tabrakan dengan ringkasan)
    plt.title(f"Layout Visual SBin - {sheet_name}", fontsize=14, pad=100, fontweight='bold')
    
    buf = io.BytesIO()
    plt.savefig(buf, format="pdf", bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf

FILE_EXCEL = "DAFTAR SBIN GUDANG BELAKANG_3.xlsx"
daftar_sheet = load_all_sheets(FILE_EXCEL)

if daftar_sheet:
    sheet_aktif = st.sidebar.selectbox("Pilih Area Gudang (SSLOC):", daftar_sheet)
    df_layout = load_rack_layout(FILE_EXCEL, sheet_aktif)
    
    if 'sbin_db' not in st.session_state:
        st.session_state.sbin_db = {}
    if 'material_jalan' not in st.session_state:
        st.session_state.material_jalan = {}
        
    if sheet_aktif not in st.session_state.sbin_db:
        st.session_state.sbin_db[sheet_aktif] = {}
        st.session_state.material_jalan[sheet_aktif] = 0
        for row in range(df_layout.shape[0]):
            for col in range(df_layout.shape[1]):
                val = str(df_layout.iat[row, col]).strip()
                if val != "" and val.upper() not in ["KANTOR", "JALAN", "PINTU", "TYPE", "RAK"]:
                    st.session_state.sbin_db[sheet_aktif][val] = False

    mode_utama = st.radio(
        "Pilih Aktivitas yang Ingin Dilakukan:", 
        ["📝 Ceklist Keterisian SBin", "🚚 Input Total Material di Jalan"],
        horizontal=True
    )
    st.markdown("---")

    if mode_utama == "📝 Ceklist Keterisian SBin":
        daftar_semua_sbin = list(st.session_state.sbin_db[sheet_aktif].keys())
        daftar_rak = sorted(list(set([k[:2] for k in daftar_semua_sbin if len(k) >= 2])))
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            rak_aktif = st.selectbox("Filter Lorong/Rak:", ["SEMUA RAK"] + daftar_rak)
        with col_f2:
            filter_status = st.radio("Fokus Tampilan:", ["Semua", "Hanya Kosong", "Hanya Terisi"], horizontal=True)

        data_list = []
        for sbin_code, terisi in st.session_state.sbin_db[sheet_aktif].items():
            if rak_aktif != "SEMUA RAK" and not sbin_code.startswith(rak_aktif):
                continue
            if filter_status == "Hanya Kosong" and terisi:
                continue
            if filter_status == "Hanya Terisi" and not terisi:
                continue
            
            data_list.append({"Kode SBin": sbin_code, "Terisi (1 Pallet)": terisi})

        if data_list:
            df_tabel = pd.DataFrame(data_list)
            tabel_diedit = st.data_editor(
                df_tabel,
                column_config={"Terisi (1 Pallet)": st.column_config.CheckboxColumn("SBin Terisi?", default=False)},
                disabled=["Kode SBin"],
                hide_index=True,
                use_container_width=True
            )
            
            if st.button("💾 Simpan Ceklist SBin", type="primary"):
                for index, row in tabel_diedit.iterrows():
                    st.session_state.sbin_db[sheet_aktif][row["Kode SBin"]] = row["Terisi (1 Pallet)"]
                st.success("Data rak berhasil diperbarui!")
                st.rerun()
        else:
            st.info("Tidak ada SBin yang sesuai dengan filter saat ini.")

    elif mode_utama == "🚚 Input Total Material di Jalan":
        st.subheader("Data Material In-Transit")
        qty_jalan = st.number_input(
            f"Total gelondongan material di jalan untuk area {sheet_aktif}:", 
            min_value=0, 
            value=st.session_state.material_jalan[sheet_aktif]
        )
        if st.button("💾 Simpan Total Material", type="primary"):
            st.session_state.material_jalan[sheet_aktif] = qty_jalan
            st.success("Total material di jalan berhasil dicatat!")
            st.rerun()

    # ==========================================
    # REKAP & PDF DOWNLOAD (Anti Lag & Dinamis)
    # ==========================================
    st.markdown("---")
    col_rekap, col_pdf = st.columns([3, 1])
    
    # Hitung Variabel Rekap
    total_sbin = len(st.session_state.sbin_db[sheet_aktif])
    tot_terisi = sum(1 for status in st.session_state.sbin_db[sheet_aktif].values() if status)
    tot_kosong = total_sbin - tot_terisi
    tot_material = st.session_state.material_jalan[sheet_aktif]

    with col_rekap:
        st.subheader("📊 Dasbor Rekapitulasi")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Kapasitas (SBin)", total_sbin)
        c2.metric("✅ SBin Terisi", tot_terisi)
        c3.metric("🚚 Material di Jalan", tot_material)

    with col_pdf:
        st.subheader("🖨️ Cetak Layout")
        st.write("Klik tombol di bawah untuk memproses PDF.")
        
        # Penamaan File Dinamis dengan Tanggal Bahasa Indonesia
        sekarang = datetime.datetime.now()
        bulan_indo = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        tgl_str = f"{sekarang.day} {bulan_indo[sekarang.month]} {sekarang.year}"
        
        nama_file_dinamis = f"sbin {sheet_aktif} data {tgl_str}.pdf"
        
        # Tombol Pemicu PDF
        if st.button("🔄 Proses Layout PDF"):
            with st.spinner("Menyiapkan ringkasan & menggambar layout..."):
                pdf_file = generate_pdf_layout(df_layout, st.session_state.sbin_db[sheet_aktif], sheet_aktif, tot_terisi, tot_kosong, tot_material, tgl_str)
                st.session_state['file_pdf_siap'] = pdf_file
                
        # Menampilkan Tombol Download
        if 'file_pdf_siap' in st.session_state:
            st.download_button(
                label="📄 Download Layout PDF",
                data=st.session_state['file_pdf_siap'],
                file_name=nama_file_dinamis,
                mime="application/pdf",
                type="primary"
            )
else:
    st.error("Gagal memuat Excel.")
