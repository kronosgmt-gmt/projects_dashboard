import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from urllib.parse import urlparse
import requests
import io

# Configuración de la página
st.set_page_config(
    page_title="Kronos GMT - Project Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado (modo oscuro)
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; background: linear-gradient(135deg, #1a252f, #2c3e50); color: #ffffff; text-align: center; padding: 1rem; border-radius: 10px; margin-bottom: 1.5rem; }
    .section-header { font-size: 1.5rem; font-weight: bold; color: #ffffff; margin: 1rem 0; border-bottom: 2px solid #07b9d1; padding-bottom: 0.5rem; }
    .nav-button { display: block; width: 100%; padding: 10px; margin: 5px 0; background-color: #34495e; color: #ffffff; text-decoration: none; border-radius: 5px; text-align: center; font-weight: bold; transition: all 0.3s ease; }
    .nav-button:hover { background-color: #2c3e50; color: #1a252f; transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
    .logo-container { text-align: center; margin-bottom: 20px; }
    .stApp { background-color: #1a252f; }
    [data-testid="stExpander"] summary { background: #34495e; color: #07b9d1 !important; border: 2px solid #07b9d1; border-radius: 8px; padding: 12px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# Configuración Cloudinary
CLOUDINARY_CLOUD_NAME = "dmbgxvfo0"

def is_valid_cloudinary_url(url, cloud_name=None):
    if not url or pd.isna(url) or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    if cloud_name:
        return parsed.netloc == "res.cloudinary.com" and url.startswith(f"https://res.cloudinary.com/{cloud_name}/")
    return parsed.netloc == "res.cloudinary.com"

@st.cache_data
def load_data():
    url = "https://github.com/kronosgmt-gmt/projects_dashboard/blob/main/proyects.csv"
    try:
        if "github.com" in url:
            url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text), encoding='utf-8')
        df.columns = df.columns.str.strip()

        # Conversión de coordenadas
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Customer_Type'] = df['Customer_Type'].fillna('Unknown')

        # Limpieza de servicios
        def clean_services(x):
            if pd.isna(x) or not x:
                return []
            try:
                x = str(x).strip()
                if x.startswith('['):
                    return [s.strip(" '") for s in x.strip("[]").split(',') if s.strip()]
                return [s.strip() for s in x.split(',') if s.strip()]
            except:
                return []

        df['Service_2_list'] = df['Service_2'].apply(clean_services) if 'Service_2' in df.columns else [[] for _ in range(len(df))]

        # Validación de columnas requeridas
        required = ['project_id', 'Project_Name', 'Longitude', 'Latitude']
        missing = [col for col in required if col not in df.columns]
        if missing:
            st.error(f"❌ Missing columns: {missing}")
            return None

        # Limpieza de coordenadas
        df.dropna(subset=['Latitude', 'Longitude'], inplace=True)
        df = df[(df['Latitude'].between(-90, 90)) & (df['Longitude'].between(-180, 180))]

        # Ajuste de URLs de imágenes
        if 'Image' in df.columns and CLOUDINARY_CLOUD_NAME:
            df['Image'] = df['Image'].apply(
                lambda x: f"https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/image/upload/{x.strip()}"
                if pd.notna(x) and isinstance(x, str) and x.strip() and not is_valid_cloudinary_url(x, CLOUDINARY_CLOUD_NAME)
                else x
            )

        return df if not df.empty else None
    except Exception as e:
        st.warning(f"⚠️ Failed to load data: {str(e)}")
        return None

def filter_data(df, project_type, service):
    filtered = df.copy()
    if project_type != "All":
        filtered = filtered[filtered['Customer_Type'] == project_type]
    if service != "All":
        filtered = filtered[filtered['Service_2_list'].apply(lambda x: service in x)]
    return filtered

def create_map(df):
    if df.empty:
        return None
    center_lat = df['Latitude'].mean()
    center_lon = df['Longitude'].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles="OpenStreetMap")
    for _, row in df.iterrows():
        popup = f"<b>{row['Project_Name']}</b><br>{row['Customer_Type']}"
        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=8,
            popup=popup,
            tooltip=row['Project_Name'],
            fillColor="#07b9d1",
            fillOpacity=0.7,
            color='white',
            weight=1
        ).add_to(m)
    return m

def create_service_chart(df):
    if df.empty:
        return None
    all_services = [s for services in df['Service_2_list'] for s in services if s]
    if not all_services:
        return None
    counts = pd.Series(all_services).value_counts()
    fig = px.pie(values=counts.values, names=counts.index, title="Services Provided")
    fig.update_traces(textinfo='percent+label')
    fig.update_layout(paper_bgcolor='#1a242e', font_color="white")
    return fig

def display_gallery(df):
    if 'Image' not in df.columns:
        return
    valid_images = df[df['Image'].apply(lambda x: is_valid_cloudinary_url(x, CLOUDINARY_CLOUD_NAME))]
    if valid_images.empty:
        st.write("🖼️ No images available in current view.")
        return
    st.markdown('<div class="section-header">🖼️ Project Gallery</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    for i, (_, row) in enumerate(valid_images.head(8).iterrows()):
        with cols[i % 4]:
            st.image(row['Image'], caption=row['Project_Name'], use_container_width=True)
            if pd.notna(row.get('Blog_Link')):
                st.markdown(f"[📖 More info]({row['Blog_Link']})", unsafe_allow_html=True)

def navigation_sidebar():
    with st.sidebar:
        st.markdown("""
        <div class="logo-container">
            <a href="https://kronosgmt.com" target="_blank">
                <img src="https://res.cloudinary.com/dmbgxvfo0/image/upload/v1754540320/Logos_Kronos_PNG-04_nxdbz3.png" 
                     style="width: 300px; border-radius: 10px;">
            </a>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### Filters")
        types = ["All"] + sorted(df['Customer_Type'].dropna().unique().tolist())
        selected_type = st.selectbox("🏢 Project Type", types, index=0, key="type_filter")
        services = ["All"] + sorted({s for lst in df['Service_2_list'] for s in lst if s})
        selected_service = st.selectbox("🛠️ Service", services, index=0, key="service_filter")
        if st.button("Reset Filters"):
            st.rerun()

        st.markdown("---")

        with st.expander("🛠️ Services", expanded=False):
            st.markdown("""<a href="https://www.kronosgmt.com/3D-rendering" target="_blank" class="nav-button">3D Rendering</a>""", unsafe_allow_html=True)
            st.markdown("""<a href="https://www.kronosgmt.com/CAD-drafting" target="_blank" class="nav-button">CAD Drafting</a>""", unsafe_allow_html=True)
            st.markdown("""<a href="https://www.kronosgmt.com/takeoffs-schedules" target="_blank" class="nav-button">Takeoffs & Schedules</a>""", unsafe_allow_html=True)
            st.markdown("""<a href="https://www.kronosgmt.com/GIS-mapping" target="_blank" class="nav-button">GIS Mapping</a>""", unsafe_allow_html=True)
            st.markdown("""<a href="https://www.kronosgmt.com/automation-workflow-optimization" target="_blank" class="nav-button">Automation & Workflow</a>""", unsafe_allow_html=True)

        st.markdown("""<a href="https://news.kronosgmt.com/" target="_blank" class="nav-button">📰 News</a>""", unsafe_allow_html=True)
        st.markdown("""<a href="https://www.kronosgmt.com/#contact" target="_blank" class="nav-button">📧 Contact Us</a>""", unsafe_allow_html=True)
        st.markdown("---")

# --- MAIN APP ---
def main():
    st.markdown('<h1 class="main-header"> Kronos GMT - Project Dashboard </h1>', unsafe_allow_html=True)

    df = load_data()
    if df is None or df.empty:
        st.error("❌ No data available.")
        st.stop()

    # Sidebar con filtros
    navigation_sidebar()

    # Filtros seleccionados
    selected_type = st.session_state.get("type_filter", "All")
    selected_service = st.session_state.get("service_filter", "All")

    filtered_df = filter_data(df, selected_type, selected_service)
    if filtered_df.empty:
        st.error("❌ No projects match the selected filters.")
        st.stop()

    # Layout principal
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown('<div class="section-header">📍 Project Location</div>', unsafe_allow_html=True)

        # Validar datos para el mapa
        map_df = filtered_df.dropna(subset=['Latitude', 'Longitude'])
        map_df = map_df[(map_df['Latitude'].between(-90, 90)) & (map_df['Longitude'].between(-180, 180))]
        if map_df.empty:
            st.warning("No valid coordinates to display.")
            st.stop()

        # Crear y mostrar mapa
        map_obj = create_map(map_df)
        if map_obj:
            map_data = st_folium(
                map_obj,
                key="main_map",
                height=500,
                use_container_width=True,
                returned_objects=["bounds"],
                sticky=True
            )
        else:
            st.warning("Unable to generate map.")
            st.stop()

    with col2:
        st.markdown('<div class="section-header">📊 Services</div>', unsafe_allow_html=True)

    # Filtrar por área visible en el mapa
    displayed_df = map_df.copy()
    if map_data and isinstance(map_data, dict) and map_data.get("bounds"):
        bounds = map_data["bounds"]
        sw, ne = bounds["southWest"], bounds["northEast"]
        lat_min, lat_max = sw["lat"], ne["lat"]
        lon_min, lon_max = sw["lng"], ne["lng"]
        displayed_df = map_df[
            (map_df['Latitude'] >= lat_min) &
            (map_df['Latitude'] <= lat_max) &
            (map_df['Longitude'] >= lon_min) &
            (map_df['Longitude'] <= lon_max)
        ]
        st.write(f"📍 **{len(displayed_df)} projects in current view**")
    else:
        st.write("🔍 Pan or zoom the map to filter")

    # Actualizar gráfico
    with col2:
        chart = create_service_chart(displayed_df)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.write("No service data.")

    # Actualizar galería
    display_gallery(displayed_df)

    st.markdown("---")
    st.caption("© 2025 Kronos GMT | Created by Juan Cano")

if __name__ == "__main__":
    main()
