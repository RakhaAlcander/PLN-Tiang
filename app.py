import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
import math
import folium 
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static
import re 
import sqlite3
def get_connection():
    return sqlite3.connect("database_material.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS material (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kategori TEXT,
            jenis_tiang TEXT,
            satuan TEXT,
            pasang REAL,
            tunai REAL,
            pln REAL,
            harga_satuan_material INTEGER,
            harga_satuan_tukang INTEGER
        )
    """)
    conn.commit()
    conn.close()

def add_or_update_material(kategori, jenis, satuan, pasang, tunai, pln, hrg_mat, hrg_tuk):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM material WHERE kategori=? AND jenis_tiang=?", (kategori, jenis))
    row = cur.fetchone()
    if row:
        cur.execute("""
            UPDATE material
            SET satuan=?, pasang=?, tunai=?, pln=?, harga_satuan_material=?, harga_satuan_tukang=?
            WHERE id=?
        """, (satuan, pasang, tunai, pln, hrg_mat, hrg_tuk, row[0]))
    else:
        cur.execute("""
            INSERT INTO material (kategori, jenis_tiang, satuan, pasang, tunai, pln, harga_satuan_material, harga_satuan_tukang)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (kategori, jenis, satuan, pasang, tunai, pln, hrg_mat, hrg_tuk))
    conn.commit()
    conn.close()

def get_all_material():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM material", conn)
    conn.close()
    return df

def delete_by_kategori(kat):
    conn = get_connection()
    conn.execute("DELETE FROM material WHERE kategori=?", (kat,))
    conn.commit()
    conn.close()

def delete_material_by_id(material_id):
    conn = sqlite3.connect('database_material.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM material WHERE id = ?", (material_id,))
    conn.commit()
    conn.close()

def format_currency(val):
    try:
        val = float(val)
        return f"Rp {val:,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return "Rp -"

# Set page config
st.set_page_config(
    page_title="Sistem RAB Tiang Listrik Enhanced",
    page_icon="🔌",
    layout="wide",
    initial_sidebar_state="expanded"
)
init_db()

# Initialize session state
if 'tiang_data' not in st.session_state:
    st.session_state.tiang_data = []

if 'tiang_awal' not in st.session_state:
    st.session_state.tiang_awal = 'TM1'

# --- Helper Functions from Notebook (for angle calculation) ---
def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculate bearing between two points."""
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lon_rad = math.radians(lon2 - lon1)
    
    x = math.sin(delta_lon_rad) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - \
        math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon_rad)
    
    bearing_rad = math.atan2(x, y)
    bearing_deg = math.degrees(bearing_rad)
    return (bearing_deg + 360) % 360

def angle_diff(b1, b2):
    """Calculate the smaller angle difference between two bearings."""
    diff = abs(b1 - b2)
    return min(diff, 360 - diff)
# --- End Helper Functions ---

# Functions from existing app.py (potentially modified)
def klasifikasi_tiang(sudut):
    """Klasifikasi tiang berdasarkan sudut (0-180 degrees from angle_diff)."""
    if sudut is None or pd.isna(sudut):
        return None
    try:
        sudut = float(sudut)
    except (ValueError, TypeError):
        return None
    
    if 0 <= sudut <= 15:
        return "TM1"
    elif 16 <= sudut <= 30:
        return "TM2"
    elif 31 <= sudut <= 60:
        return "TM5"
    elif 61 <= sudut <= 180: # angle_diff ensures sudut <= 180
        return "TM10"
    else:
        # This case should ideally not be reached if angle_diff is used
        return None 

def standardize_kategori(kategori):
    """Standardisasi kategori dari Excel - DIPERBAIKI"""
    if not kategori or pd.isna(kategori):
        return None
    kategori_str = str(kategori).upper().strip()
    kategori_clean = kategori_str.replace(' ', '').replace('-', '').replace('_', '')
    
    if kategori_clean == 'TM1' or 'TM1' in kategori_clean: return 'TM1'
    elif kategori_clean == 'TM2' or 'TM2' in kategori_clean: return 'TM2'
    elif kategori_clean == 'TM5' or 'TM5' in kategori_clean: return 'TM5'
    elif kategori_clean == 'TM10' or 'TM10' in kategori_clean: return 'TM10'
    elif kategori_clean == 'TM4' or 'TM4' in kategori_clean: return 'TM4' # Usually for end pole
    return None

def read_file_flexible(uploaded_file):
    """Baca file dengan format xlsx, xls, atau csv"""
    try:
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension == 'csv':
            # Try common delimiters for CSV
            try:
                df = pd.read_csv(uploaded_file, sep=None, engine='python') # engine='python' enables sep=None
            except pd.errors.ParserError:
                 df = pd.read_csv(uploaded_file) # Fallback to comma
        elif file_extension in ['xlsx', 'xls']:
            df = pd.read_excel(uploaded_file)
        else:
            st.error("Format file tidak didukung. Gunakan xlsx, xls, atau csv.")
            return None
        return df
    except Exception as e:
        st.error(f"Error membaca file: {str(e)}")
        return None

def parse_database_material(df):
    """Parse database material dari Excel/CSV"""
    database_material = {}
    current_kategori_context = None # Renamed to avoid confusion with loop variables
    
    # Try to identify the main column for "Jenis Tiang"
    jenis_tiang_col_name = None
    possible_jt_cols = ['Jenis Tiang', 'jenis_tiang', 'Material', 'Deskripsi', 'Uraian Pekerjaan'] # Added more possibilities
    for col in df.columns:
        col_lower = col.lower()
        if any(p_col.lower() in col_lower for p_col in possible_jt_cols):
            jenis_tiang_col_name = col
            break
    if jenis_tiang_col_name is None and len(df.columns) > 0: 
        # Fallback: assume the second column if multiple, or first if only one.
        # This might need adjustment if the Excel structure is very different.
        jenis_tiang_col_name = df.columns[1] if len(df.columns) > 1 else df.columns[0]


    for idx, row in df.iterrows():
        # Ensure the identified column actually exists in the row
        if jenis_tiang_col_name not in row:
            # st.warning(f"Kolom '{jenis_tiang_col_name}' tidak ditemukan di baris {idx+2}. Baris dilewati.")
            continue
            
        cell_value_str = str(row[jenis_tiang_col_name]).upper().strip()
        
        is_category_header_row = False
        identified_category_for_this_header = None
        
        # Regex based category identification
        cat_keys_to_scan = ['TM1', 'TM2', 'TM5', 'TM10', 'TM4'] 
        for cat_key_item in cat_keys_to_scan:
            num_part = cat_key_item[2:]  # e.g., "1", "10"
            # Pattern: TM, optional space/hyphen, number part, word boundary
            # This helps distinguish TM1 from TM10, etc.
            # Also allow for "KONSTRUKSI" or "PEKERJAAN" before TM
            pattern = rf"(?:KONSTRUKSI|PEKERJAAN)?[-\s]*TM[-\s]?{num_part}\b"
            if re.search(pattern, cell_value_str):
                identified_category_for_this_header = cat_key_item
                break 
        
        if identified_category_for_this_header:
            current_kategori_context = identified_category_for_this_header
            # Initialize an empty list for this category if it's the first time we see this header
            if current_kategori_context not in database_material:
                database_material[current_kategori_context] = []
            is_category_header_row = True
        
        if is_category_header_row:
            continue # Skip to the next row, as this was a header

        # If this row is not a header, and we have an active category context, parse it as a material item
        if current_kategori_context and not is_category_header_row:
            try:
                # Skip if jenis_tiang is empty or clearly a sub-header/comment
                if cell_value_str in ['', 'NAN'] or \
                   any(skip_kw in cell_value_str for skip_kw in ["PEKERJAAN UTAMA", "ACCESORIES", "SUB TOTAL", "TOTAL"]):
                    continue

                material_item = {
                    'no': len(database_material[current_kategori_context]) + 1,
                    'jenis_tiang': str(row.get(jenis_tiang_col_name, '')).strip(), # Use original case from cell_value_str's source if needed
                    'satuan': str(row.get('Satuan', row.get('SAT', row.get('Unit', 'Bh')))).strip(), # Added 'Unit', default 'Bh'
                    'pasang': float(row.get('Pasang', row.get('PASANG', row.get('Volume', row.get('Qty', 1))))), # Added 'Qty'
                    'tunai': float(row.get('Tunai', row.get('TUNAI', row.get('Volume', row.get('Qty', 1))))),
                    'pln': float(row.get('PLN', row.get('pln', row.get('Volume', row.get('Qty', 1))))),
                    'harga_satuan_material': float(row.get('Harga Satuan Material', row.get('HARGA SATUAN MATERIAL', row.get('Harga Material', row.get('Harga Satuan (Material)',0))))),
                    'harga_satuan_tukang': float(row.get('Harga Satuan Tukang', row.get('HARGA SATUAN TUKANG', row.get('Harga Tukang', row.get('Harga Satuan (Jasa)',0)))))
                }
                
                database_material[current_kategori_context].append(material_item)
            except (ValueError, TypeError, KeyError) as e:
                # st.warning(f"Melewatkan baris material ({cell_value_str}) di database karena error parsing: {e}")
                continue
    return database_material

def calculate_rab_detail(jumlah_tiang_per_kategori):
    """Hitung RAB detail berdasarkan database material (versi SQLite)"""
    rab_detail = {}
    df_material = get_all_material()

    for kategori, jumlah_tiang in jumlah_tiang_per_kategori.items():
        df_kat = df_material[df_material['kategori'] == kategori]
        if df_kat.empty:
            continue

        rab_detail[kategori] = []
        for i, row in df_kat.iterrows():
            total_pasang = row['pasang'] * jumlah_tiang
            total_tunai = row['tunai'] * jumlah_tiang
            total_pln = row['pln'] * jumlah_tiang

            jumlah_harga_material = row['harga_satuan_material'] * total_pasang
            jumlah_harga_tukang = row['harga_satuan_tukang'] * total_pasang
            total_harga = jumlah_harga_material + jumlah_harga_tukang

            rab_item = {
                'no': i + 1,
                'jenis_tiang': row['jenis_tiang'],
                'satuan': row['satuan'],
                'pasang': total_pasang,
                'tunai': total_tunai,
                'pln': total_pln,
                'harga_satuan_material': row['harga_satuan_material'],
                'harga_satuan_tukang': row['harga_satuan_tukang'],
                'jumlah_harga_material': jumlah_harga_material,
                'jumlah_harga_tukang': jumlah_harga_tukang,
                'total': total_harga
            }
            rab_detail[kategori].append(rab_item)
    return rab_detail

def format_currency(val):
    try:
        val = float(val)
        return f"Rp {val:,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return "Rp -"

def get_marker_color(kategori):
    """Get marker color based on kategori tiang"""
    color_map = {
        'TM1': 'green',
        'TM2': 'blue', 
        'TM5': 'orange',
        'TM10': 'red',
        'TM4': 'purple'
    }
    return color_map.get(kategori, 'gray')

def create_map_with_tiang_data(tiang_data):
    """Create Folium map with tiang data"""
    if not tiang_data:
        st.info("Tidak ada data tiang untuk ditampilkan di peta")
        return None
    
    # Filter data yang memiliki koordinat valid
    valid_coords = [t for t in tiang_data if t.get('latitude') is not None and t.get('longitude') is not None]
    
    if not valid_coords:
        st.warning("Tidak ada data tiang dengan koordinat valid untuk ditampilkan di peta")
        return None
    
    # Calculate center of map
    center_lat = sum(t['latitude'] for t in valid_coords) / len(valid_coords)
    center_lon = sum(t['longitude'] for t in valid_coords) / len(valid_coords)
    
    # Create map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
        tiles="OpenStreetMap"
    )
    
    # Add markers for each tiang
    for i, tiang in enumerate(valid_coords):
        kategori = tiang.get('kategori_final', tiang.get('kategori', 'Unknown'))
        color = get_marker_color(kategori)
        
        # Create popup content
        popup_html = f"""
        <div style="width: 250px;">
            <h4>{tiang.get('nama', f'Tiang {i+1}')}</h4>
            <p><b>Koordinat:</b> {tiang['latitude']:.6f}, {tiang['longitude']:.6f}</p>
            <p><b>Kategori:</b> {kategori}</p>
            <p><b>Sudut:</b> {tiang.get('sudut', 'N/A')}°</p>
            <p><b>Posisi:</b> {tiang.get('posisi', 'N/A')}</p>
            <p><b>Sumber:</b> {tiang.get('source_type', 'Manual')}</p>
        </div>
        """
        
        folium.Marker(
            location=[tiang['latitude'], tiang['longitude']],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{tiang.get('nama', f'Tiang {i+1}')} ({kategori})",
            icon=folium.Icon(color=color, icon='flash', prefix='fa')
        ).add_to(m)
    
    # Add polyline connecting all points (route)
    if len(valid_coords) > 1:
        coords = [[t['latitude'], t['longitude']] for t in valid_coords]
        folium.PolyLine(
            coords,
            color='blue',
            weight=3,
            opacity=0.7,
            popup="Jalur Tiang Listrik"
        ).add_to(m)
    
    # Add legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 200px; height: 160px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <h4>Kategori Tiang</h4>
    <p><i class="fa fa-flash" style="color:green"></i> TM1 (0°-15°)</p>
    <p><i class="fa fa-flash" style="color:blue"></i> TM2 (16°-30°)</p>
    <p><i class="fa fa-flash" style="color:orange"></i> TM5 (31°-60°)</p>
    <p><i class="fa fa-flash" style="color:red"></i> TM10 (61°-180°)</p>
    <p><i class="fa fa-flash" style="color:purple"></i> TM4 (Akhir)</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    return m

def process_tiang_data():
    """Process tiang data for klasifikasi and RAB, returning updated tiang list and counts."""
    if not st.session_state.tiang_data:
        return [], {}, {} 

    tiang_final_list = [] 
    
    for i, tiang_original in enumerate(st.session_state.tiang_data):
        tiang = tiang_original.copy() 
        posisi = 'awal' if i == 0 else 'akhir' if i == len(st.session_state.tiang_data) - 1 else 'tengah'
        
        if posisi == 'awal':
            tiang['kategori_final'] = st.session_state.tiang_awal
        elif posisi == 'akhir':
            tiang['kategori_final'] = 'TM4' 
        else:
            if tiang.get('kategori') is None and tiang.get('sudut') is not None:
                tiang['kategori_final'] = klasifikasi_tiang(tiang['sudut'])
            elif tiang.get('kategori') is not None:
                tiang['kategori_final'] = tiang['kategori']
            else: 
                tiang['kategori_final'] = None 
        tiang['posisi'] = posisi
        tiang_final_list.append(tiang)
    
    klasifikasi_count = {}
    for tiang in tiang_final_list:
        kategori = tiang['kategori_final']
        if kategori: 
            klasifikasi_count[kategori] = klasifikasi_count.get(kategori, 0) + 1
            
    rab_detail_calculated = calculate_rab_detail(klasifikasi_count)
    
    return tiang_final_list, klasifikasi_count, rab_detail_calculated

def export_to_excel(tiang_final_list, klasifikasi, rab_detail):
    """Export data ke Excel"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if tiang_final_list:
            export_tiang_data = []
            for i, tiang in enumerate(tiang_final_list):
                export_tiang_data.append({
                    'No': i + 1,
                    'Latitude': tiang.get('latitude'),
                    'Longitude': tiang.get('longitude'),
                    'Label': tiang.get('nama', f'Tiang {i + 1}'),
                    'Sudut (derajat)': tiang.get('sudut'),
                    'Kategori_Asli_File': tiang.get('kategori_asli', ''),
                    'Kategori_dari_Sudut': klasifikasi_tiang(tiang.get('sudut')) if tiang.get('sudut') is not None else '',
                    'Kategori_Interim': tiang.get('kategori', ''),
                    'Kategori_Final': tiang.get('kategori_final', ''),
                    'Posisi': tiang.get('posisi', ''),
                    'Sumber_Data': tiang.get('source_type', 'Manual Input' if not tiang.get('from_excel') else 'File Import')
                })
            tiang_df = pd.DataFrame(export_tiang_data)
            tiang_df.to_excel(writer, sheet_name='Data Tiang', index=False)
        
        if klasifikasi:
            klasifikasi_df = pd.DataFrame([{'Kategori': k, 'Jumlah': v} for k, v in klasifikasi.items()])
            klasifikasi_df.to_excel(writer, sheet_name='Klasifikasi', index=False)
        
        if rab_detail:
            rab_df_data = []
            for kategori, items in rab_detail.items():
                for item in items:
                    rab_df_data.append({
                        'Kategori': kategori, 'No': item['no'], 'Jenis Tiang': item['jenis_tiang'], 
                        'Satuan': item['satuan'], 'Pasang': item['pasang'], 'Tunai': item['tunai'], 'PLN': item['pln'],
                        'Harga Satuan Material': item['harga_satuan_material'],
                        'Harga Satuan Tukang': item['harga_satuan_tukang'],
                        'Jumlah Harga Material': item['jumlah_harga_material'],
                        'Jumlah Harga Tukang': item['jumlah_harga_tukang'],
                        'Total': item['total']
                    })
            if rab_df_data:
                pd.DataFrame(rab_df_data).to_excel(writer, sheet_name='RAB Detail', index=False)

        db_material_data = []
        if hasattr(st.session_state, 'database_material') and st.session_state.database_material: # Check if exists and not empty
            for kategori, materials in st.session_state.database_material.items():
                for material in materials:
                    db_material_data.append({
                        'Kategori': kategori, 'No': material['no'], 'Jenis Tiang': material['jenis_tiang'],
                        'Satuan': material['satuan'], 'Pasang': material['pasang'], 'Tunai': material['tunai'],
                        'PLN': material['pln'], 'Harga Material': material.get('harga_satuan_material',0), # Use .get for safety
                        'Harga Tukang': material.get('harga_satuan_tukang',0)
                    })
        if db_material_data: # Ensure list is not empty before creating DataFrame
            pd.DataFrame(db_material_data).to_excel(writer, sheet_name='Database Material', index=False)
            
    output.seek(0)
    return output

# Main App
def main():
    st.title("🔌 Sistem RAB Tiang Listrik Enhanced")
    st.markdown("**Klasifikasi otomatis tiang listrik dan perhitungan RAB detail terintegrasi**") 
    st.divider()
    
    with st.sidebar:
        st.header("⚙️ Pengaturan")
        st.session_state.tiang_awal = st.selectbox(
            "Pilih kategori tiang awal:",
            options=['TM1', 'TM2', 'TM5', 'TM10', 'TM4'], 
            index=['TM1', 'TM2', 'TM5', 'TM10', 'TM4'].index(st.session_state.tiang_awal if st.session_state.tiang_awal in ['TM1','TM2','TM5','TM10','TM4'] else 'TM1')
        )
        st.divider()
        st.subheader("📊 Kriteria Klasifikasi Sudut")
        st.markdown("""
        - **TM1**: 0° - 15°
        - **TM2**: 16° - 30°  
        - **TM5**: 31° - 60°
        - **TM10**: 61° - 180°
        - **TM4**: Tiang Akhir *(otomatis)*
        """)
        st.info("💡 **Catatan**: Sistem mendukung format Excel (.xlsx, .xls) dan CSV (.csv). Sudut dapat dihitung otomatis jika tersedia data Latitude & Longitude.")

    tab_titles = ["📤 Import Data", "📊 Hasil & RAB", "🗃️ Database Material", "⬇️ Export"]
    tab1, tab2, tab3, tab4 = st.tabs(tab_titles) 
    
    with tab1:
        col1, col2 = st.columns(2)
        with col1: 
            st.header("📤 Import Data Tiang")
            uploaded_tiang_file = st.file_uploader(
                "Upload file data tiang (Excel/CSV)",
                type=['xlsx', 'xls', 'csv'],
                help="Kolom yang diharapkan: Latitude, Longitude, Label (Nama), Sudut (derajat), Kategori (opsional). Jika Sudut kosong & Lat/Lon ada, sudut dihitung.",
                key="tiang_uploader"
            )

            if uploaded_tiang_file is not None:
                df_input = read_file_flexible(uploaded_tiang_file)
                if df_input is not None:
                    col_map_candidates = {
                        'Latitude': ['Latitude', 'latitude', 'Lat', 'Y'],
                        'Longitude': ['Longitude', 'longitude', 'Lon', 'Long', 'X'],
                        'Label': ['Label', 'label', 'Nama Tiang', 'Nama', 'Name', 'ID Tiang', 'ID'],
                        'Sudut': ['Sudut (derajat)', 'Sudut', 'sudut', 'Angle', 'Derajat'],
                        'Kategori': ['Kategori', 'kategori', 'Jenis Tiang', 'Jenis', 'Type', 'Tipe']
                    }
                    
                    df_renamed = df_input.copy()

                    for standard_col, potential_names in col_map_candidates.items():
                        for p_name in potential_names:
                            if p_name in df_renamed.columns:
                                if p_name != standard_col : 
                                     df_renamed = df_renamed.rename(columns={p_name: standard_col}, errors='ignore')
                                break
                    
                    if 'Latitude' in df_renamed.columns:
                        df_renamed['Latitude'] = pd.to_numeric(df_renamed['Latitude'], errors='coerce')
                    if 'Longitude' in df_renamed.columns:
                        df_renamed['Longitude'] = pd.to_numeric(df_renamed['Longitude'], errors='coerce')

                    can_calc_angles = ('Latitude' in df_renamed.columns and df_renamed['Latitude'].notna().any() and \
                                       'Longitude' in df_renamed.columns and df_renamed['Longitude'].notna().any())
                    
                    perform_angle_calc = False
                    if can_calc_angles:
                        if 'Sudut' not in df_renamed.columns or df_renamed['Sudut'].isna().all():
                            st.info("Kolom 'Sudut' tidak ada atau kosong, menghitung dari koordinat...")
                            perform_angle_calc = True
                    
                    if perform_angle_calc and len(df_renamed) >= 3:
                        df_renamed['Sudut_Calculated'] = pd.NA 
                        for i in range(1, len(df_renamed) - 1):
                            try:
                                p1 = df_renamed.iloc[i-1]
                                p2 = df_renamed.iloc[i]
                                p3 = df_renamed.iloc[i+1]
                                if pd.notna(p1.get('Latitude')) and pd.notna(p1.get('Longitude')) and \
                                   pd.notna(p2.get('Latitude')) and pd.notna(p2.get('Longitude')) and \
                                   pd.notna(p3.get('Latitude')) and pd.notna(p3.get('Longitude')):
                                    
                                    bearing1 = calculate_bearing(p1['Latitude'], p1['Longitude'], p2['Latitude'], p2['Longitude'])
                                    bearing2 = calculate_bearing(p2['Latitude'], p2['Longitude'], p3['Latitude'], p3['Longitude'])
                                    angle = angle_diff(bearing1, bearing2)
                                    df_renamed.loc[df_renamed.index[i], 'Sudut_Calculated'] = round(angle, 2)
                                else:
                                     df_renamed.loc[df_renamed.index[i], 'Sudut_Calculated'] = pd.NA
                            except Exception as e:
                                # st.warning(f"Gagal menghitung sudut untuk baris {i}: {e}")
                                df_renamed.loc[df_renamed.index[i], 'Sudut_Calculated'] = pd.NA
                                continue
                        df_renamed['Sudut'] = df_renamed['Sudut_Calculated']
                        if 'Sudut_Calculated' in df_renamed.columns: # Ensure column exists before dropping
                            df_renamed = df_renamed.drop(columns=['Sudut_Calculated'])
                    elif 'Sudut' in df_renamed.columns: 
                        df_renamed['Sudut'] = pd.to_numeric(df_renamed['Sudut'], errors='coerce')
                    else: 
                        df_renamed['Sudut'] = pd.NA

                    temp_tiang_data = []
                    for i, row_dict_original in enumerate(df_renamed.to_dict(orient='records')):
                        # Ensure all expected keys from col_map_candidates are accessed safely using .get()
                        row_dict = {k: row_dict_original.get(k) for k in df_renamed.columns}

                        sudut_val = row_dict.get('Sudut')
                        sudut_val = float(sudut_val) if pd.notna(sudut_val) else None
                        kategori_asli_val = str(row_dict.get('Kategori', '')) 
                        interim_kategori = None
                        kategori_standard_val = standardize_kategori(kategori_asli_val)
                        
                        if kategori_standard_val: 
                            interim_kategori = kategori_standard_val
                        elif sudut_val is not None: 
                            interim_kategori = klasifikasi_tiang(sudut_val)
                        
                        temp_tiang_data.append({
                            'id': f"file_{df_renamed.index[i] if hasattr(df_renamed, 'index') and i < len(df_renamed.index) else i}",
                            'latitude': row_dict.get('Latitude') if pd.notna(row_dict.get('Latitude')) else None,
                            'longitude': row_dict.get('Longitude') if pd.notna(row_dict.get('Longitude')) else None,
                            'nama': str(row_dict.get('Label', f'Tiang File {i+1}')),
                            'sudut': sudut_val,
                            'kategori_asli': kategori_asli_val,
                            'kategori': interim_kategori, 
                            'from_excel': True,
                            'source_type': 'File Import'
                        })
                    st.session_state.tiang_data = temp_tiang_data
                    st.success(f"✅ Berhasil import dan proses {len(st.session_state.tiang_data)} data tiang!")
                    st.dataframe(df_renamed.head(), use_container_width=True) 

            st.divider()
            # st.subheader("✏️ Input Manual Data Tiang")
            # with st.form("input_tiang_form"):
            #     manual_sudut = st.number_input("Sudut Kemiringan (°)", min_value=0.0, max_value=180.0, step=0.1, value=0.0, format="%.1f")
            #     manual_nama = st.text_input("Nama Tiang (opsional)", f"Tiang Manual {len(st.session_state.tiang_data) + 1}")
            #     manual_lat = st.number_input("Latitude (opsional)", value=None, format="%.6f")
            #     manual_lon = st.number_input("Longitude (opsional)", value=None, format="%.6f")
            #     submitted_manual = st.form_submit_button("➕ Tambah Tiang")

            #     if submitted_manual:
            #         interim_cat = klasifikasi_tiang(manual_sudut)
            #         new_tiang_id = f"manual_{datetime.now().timestamp()}" 
            #         st.session_state.tiang_data.append({
            #             'id': new_tiang_id,
            #             'latitude': manual_lat, 'longitude': manual_lon,
            #             'nama': manual_nama or f"Tiang Manual {len(st.session_state.tiang_data) +1 }", 
            #             'sudut': manual_sudut,
            #             'kategori_asli': "Input Manual",
            #             'kategori': interim_cat,
            #             'from_excel': False,
            #             'source_type': 'Manual Input'
            #         })
            #         st.success(f"✅ Tiang '{manual_nama}' ditambahkan dengan kategori interim {interim_cat or 'N/A'}.")
            #         st.rerun()
    
    tiang_final_processed, klasifikasi_counts_processed, rab_detail_processed = process_tiang_data()

    with tab2:
        st.header("📊 Hasil Klasifikasi & RAB")
        col_list, col_summary = st.columns([2,3])

        with col_list:
            st.subheader(f"📋 Daftar Tiang ({len(tiang_final_processed)})")
            if tiang_final_processed:
                for i, tiang_p in enumerate(tiang_final_processed):
                    # Removed key from st.container here
                    with st.container(border=True): 
                        c1,c2 = st.columns([0.8,0.2])
                        c1.markdown(f"""
                        **{tiang_p.get('nama', f'Tiang {i+1}')}** | Kategori Final: **{tiang_p.get('kategori_final', 'N/A')}** <br>
                        📐 Sudut: {tiang_p.get('sudut', 'N/A')}° | 📍 Posisi: {tiang_p.get('posisi','N/A')}  
                        <small>Lat: {tiang_p.get('latitude', 'N/A')}, Lon: {tiang_p.get('longitude', 'N/A')}</small><br>
                        <small><i>Sumber: {tiang_p.get('source_type', 'N/A')}</i></small>
                        """, unsafe_allow_html=True)
                        if c2.button("🗑️", key=f"delete_{tiang_p['id']}", help="Hapus tiang ini"):
                            st.session_state.tiang_data = [t for t in st.session_state.tiang_data if t['id'] != tiang_p['id']]
                            st.rerun()
                if st.button("🗑️ Hapus Semua Tiang", type="secondary", use_container_width=True, key="hapus_semua_tiang_tab2"):
                    st.session_state.tiang_data = []
                    st.rerun()
            else:
                st.info("Belum ada data tiang.")
        
        with col_summary:
            if klasifikasi_counts_processed:
                st.subheader("🎯 Hasil Klasifikasi Tiang")
                num_categories = len(klasifikasi_counts_processed)
                metric_cols = st.columns(num_categories if num_categories > 0 else 1)
                col_idx = 0
                for kategori_sum, jumlah_sum in klasifikasi_counts_processed.items(): # Renamed to avoid conflict
                    metric_cols[col_idx % num_categories].metric(kategori_sum, f"{jumlah_sum} unit")
                    col_idx +=1
            else:
                 st.info("Belum ada hasil klasifikasi.")

            st.divider()

            if rab_detail_processed:
                st.subheader("💰 Ringkasan Rencana Anggaran Biaya (RAB)")
                grand_total_rab = sum(sum(item['total'] for item in items_rab) for items_rab in rab_detail_processed.values()) # Renamed items
                
                num_rab_categories = len(rab_detail_processed)
                summary_rab_cols = st.columns(num_rab_categories if num_rab_categories > 0 else 1)
                col_idx_rab = 0
                for kategori_rab, items_rab_detail in rab_detail_processed.items(): # Renamed
                    cat_total = sum(item['total'] for item in items_rab_detail)
                    current_col_rab = summary_rab_cols[col_idx_rab % num_rab_categories if num_rab_categories > 0 else 0]
                    current_col_rab.metric(
                        f"{kategori_rab}", format_currency(cat_total), f"{len(items_rab_detail)} items"
                    )
                    col_idx_rab +=1
                
                st.metric("💰 **GRAND TOTAL RAB**", format_currency(grand_total_rab), label_visibility="visible")
                
                st.divider()
                st.subheader("📋 Detail RAB per Kategori")
                for kategori_rab_detail, items_rab_cat_detail in rab_detail_processed.items(): # Renamed
                    cat_total_val = sum(item['total'] for item in items_rab_cat_detail)
                    with st.expander(f"📦 {kategori_rab_detail} - {format_currency(cat_total_val)} ({len(items_rab_cat_detail)} items)"):
                        df_rab_cat = pd.DataFrame(items_rab_cat_detail)
                        for col_curr in ['harga_satuan_material', 'harga_satuan_tukang', 'jumlah_harga_material', 'jumlah_harga_tukang', 'total']:
                            if col_curr in df_rab_cat.columns:
                                df_rab_cat[col_curr] = df_rab_cat[col_curr].apply(format_currency)
                        st.dataframe(df_rab_cat[['no', 'jenis_tiang', 'satuan', 'pasang', 'total']], hide_index=True, use_container_width=True) # Simplified view
            else:
                st.info("Belum ada detail RAB untuk ditampilkan.")

    with tab3:
        st.header("🗃️ Database Material Tersimpan")
        st.subheader("➕ Tambah/Edit Material")
    
        # Ambil kategori unik dari database
        df_material_all = get_all_material()
        kategori_list = sorted(df_material_all['kategori'].unique()) if not df_material_all.empty else []
    
        with st.form("add_material_form_tab3"): 
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                mat_kategori_input = st.selectbox(
                    "Kategori Tiang", 
                    kategori_list + ["Kategori Baru..."], 
                    key="mat_cat_select_tab3"
                )
                if mat_kategori_input == "Kategori Baru...":
                    mat_kategori_input = st.text_input("Nama Kategori Baru:", key="mat_cat_new_tab3").upper().replace(" ","")
    
                mat_jenis_input = st.text_input("Jenis Material/Pekerjaan", key="mat_jenis_tab3")
                mat_satuan_input = st.text_input("Satuan", value="B", key="mat_satuan_tab3")
            with col_m2:
                mat_pasang_input = st.number_input("Volume Pasang", min_value=0.0, value=1.0, step=0.1, key="mat_pasang_tab3")
                mat_tunai_input = st.number_input("Volume Tunai", min_value=0.0, value=1.0, step=0.1, key="mat_tunai_tab3")
                mat_pln_input = st.number_input("Volume PLN", min_value=0.0, value=1.0, step=0.1, key="mat_pln_tab3")
            with col_m3:
                mat_harga_material_input = st.number_input("Harga Satuan Material (Rp)", min_value=0, value=0, step=100, key="mat_hrg_mat_tab3")
                mat_harga_tukang_input = st.number_input("Harga Satuan Tukang (Rp)", min_value=0, value=0, step=100, key="mat_hrg_tuk_tab3")
            
            submitted_add_material = st.form_submit_button("➕ Tambah/Update Material")
    
            if submitted_add_material and mat_kategori_input and mat_jenis_input:
                add_or_update_material(
                    mat_kategori_input,
                    mat_jenis_input,
                    mat_satuan_input,
                    mat_pasang_input,
                    mat_tunai_input,
                    mat_pln_input,
                    mat_harga_material_input,
                    mat_harga_tukang_input
                )
                st.success(f"Material '{mat_jenis_input}' berhasil ditambahkan/diperbarui ke kategori {mat_kategori_input}.")
                st.rerun()
    
        st.divider()
        st.subheader("📋 Daftar Material Saat Ini")
    
        df = get_all_material()
        
        if df.empty:
            st.info("Database material kosong. Silakan tambahkan material.")
        else:
            for kategori_db_view in df['kategori'].unique():
                df_kat = df[df['kategori'] == kategori_db_view].copy()
        
                # Format harga sebelum tampil
                df_kat_display = df_kat.copy()
                for col_curr in ['harga_satuan_material', 'harga_satuan_tukang']:
                    if col_curr in df_kat_display.columns:
                        df_kat_display[col_curr] = df_kat_display[col_curr].apply(format_currency)
        
                with st.expander(f"Kategori: {kategori_db_view} ({len(df_kat)} items)"):
                    st.dataframe(
                        df_kat_display.drop(columns=['id']),
                        hide_index=True,
                        use_container_width=True
                    )
        
                    st.subheader("Hapus Material per Item:")
                    for index, row in df_kat.iterrows():
                        if st.button(f"🗑️ Hapus '{row['jenis_tiang']}'", key=f"delete_row_{row['id']}"):
                            delete_material_by_id(row['id'])
                            st.success(f"Material '{row['jenis_tiang']}' dihapus.")
                            st.rerun()
        
                    st.divider()
                    if st.button(f"🗑️ Hapus Semua Material di {kategori_db_view}", key=f"delete_all_{kategori_db_view}_tab3"):
                        delete_by_kategori(kategori_db_view)
                        st.rerun()

                        
    
    with tab4:
        st.header("⬇️ Export Data ke Excel")
        if not tiang_final_processed:
            st.warning("Tidak ada data tiang untuk diekspor. Silakan import atau input data tiang terlebih dahulu.")
        else:
            col_exp_stats1, col_exp_stats2, col_exp_stats3 = st.columns(3)
            col_exp_stats1.metric("Total Tiang Diproses", len(tiang_final_processed))
            col_exp_stats2.metric("Jumlah Kategori Tiang", len(klasifikasi_counts_processed if klasifikasi_counts_processed else {})) # Safety check
            total_rab_val = sum(sum(item_exp['total'] for item_exp in items_exp) for items_exp in rab_detail_processed.values()) if rab_detail_processed else 0 # Renamed
            col_exp_stats3.metric("Total Estimasi RAB", format_currency(total_rab_val))

            st.divider()
            
            excel_bytes = export_to_excel(tiang_final_processed, klasifikasi_counts_processed, rab_detail_processed)
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_filename = f"RAB_Tiang_Listrik_{timestamp_str}.xlsx"
            
            st.download_button(
                label="📥 Download File Excel Lengkap",
                data=excel_bytes,
                file_name=excel_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )
            st.caption("File Excel akan berisi sheet: Data Tiang, Klasifikasi, RAB Detail, dan Database Material.")


if __name__ == "__main__":
    main()
