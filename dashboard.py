import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from urllib.parse import urlparse
import requests
import io

# Config
CLOUDINARY_CLOUD_NAME = "dmbgxvfo0"
st.set_page_config(
    page_title="Kronos GMT Project's Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Funciones auxiliares
def get_project_type_colors(customer_types):
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    valid_types = [t for t in customer_types if pd.notna(t)]
    return {t: colors[i % len(colors)] for i, t in enumerate(valid_types)}

def is_valid_cloudinary_url(url, cloud_name=None):
    if not url or pd.isna(url) or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    if cloud_name:
        return parsed.netloc == "res.cloudinary.com" and url.startswith(f"https://res.cloudinary.com/{cloud_name}/")
    return parsed.netloc == "res.cloudinary.com"

@st.cache_data
def load_data():
    url = "https://raw.githubusercontent.com/kronosgmt-gmt/projects_dashboard/main/proyects.csv"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        content = io.StringIO(response.text)
        df = pd.read_csv(content, encoding='utf-8')

        if df.empty:
            st.error("Loaded data is empty")
            return None

        df.columns = df.columns.str.strip()
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        if 'Customer_Type' in df.columns:
            df['Customer_Type'] = df['Customer_Type'].fillna('Unknown')
        else:
            df['Customer_Type'] = 'Unknown'

        def clean_services(x):
            if pd.isna(x) or not x:
                return []
            if isinstance(x, str):
                if x.startswith('['):
                    return [s.strip(" '") for s in x.strip("[]").split(',') if s.strip()]
                return [s.strip() for s in x.split(',') if s.strip()]
            return []

        if 'Service_2' in df.columns:
            df['Service_2_list'] = df['Service_2'].apply(clean_services)
        else:
            df['Service_2_list'] = [[] for _ in range(len(df))]

        df.dropna(subset=['Longitude', 'Latitude'], inplace=True)
        df = df[(df['Latitude'].between(-90, 90)) & (df['Longitude'].between(-180, 180))]

        if 'Image' in df.columns and CLOUDINARY_CLOUD_NAME:
            df['Image'] = df['Image'].apply(
                lambda x: f"https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/image/upload/f_auto,q_auto,w_300,c_fill,g_auto/{x.strip()}"
                if pd.notna(x) and isinstance(x, str) and x.strip() and not is_valid_cloudinary_url(x, CLOUDINARY_CLOUD_NAME)
                else x
            )

        return df
    except (requests.RequestException, pd.errors.ParserError) as e:
        st.error(f"Failed to load data: {str(e)}")
        return None

@st.cache_data
def create_service_mapping(df):
    all_services = set()
    for services in df['Service_2_list']:
        if isinstance(services, list):
            all_services.update(services)
    return sorted([s for s in all_services if s])

@st.cache_data
def filter_data(df, project_type_filter, service_filter):
    filtered_df = df.copy()
    if project_type_filter != "All":
        filtered_df = filtered_df[filtered_df['Customer_Type'] == project_type_filter]
    if service_filter != "All":
        filtered_df = filtered_df[filtered_df['Service_2_list'].apply(lambda x: service_filter in x)]
    return filtered_df

@st.cache_data(hash_funcs={pd.DataFrame: id})
def create_interactive_map(df, initial_center, initial_zoom):
    if df.empty:
        st.warning("No data available for map")
        return None
    unique_types = df['Customer_Type'].dropna().unique()
    color_map = get_project_type_colors(unique_types)
    m = folium.Map(
        location=initial_center,
        zoom_start=initial_zoom,
        zoom_control=True,
        scrollWheelZoom=True,
        tiles="CartoDB Positron",
        attr="CartoDB"
    )
    for _, row in df.iterrows():
        popup = f"<b>{row['Project_Name']}</b><br>Type: {row['Customer_Type']}"
        color = color_map.get(row['Customer_Type'], '#888888')
        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=8,
            popup=folium.Popup(popup, max_width=300),
            tooltip=row['Project_Name'],
            fillColor=color,
            fillOpacity=0.7,
            color='white',
            weight=1
        ).add_to(m)
    return m

@st.cache_data
def create_service_distribution(df):
    if df.empty:
        return None
    all_services = [s for services in df['Service_2_list'] for s in services if s]
    if not all_services:
        return None
    counts = pd.Series(all_services).value_counts()
    fig = px.pie(values=counts.values, names=counts.index, title="Services")
    fig.update_traces(textinfo='percent+label')
    fig.update_layout(paper_bgcolor='#1a242e')
    return fig

def display_project_gallery(df):
    if 'Image' not in df.columns:
        return
    projects = df[df['Image'].apply(lambda x: is_valid_cloudinary_url(x, CLOUDINARY_CLOUD_NAME))]
    if projects.empty:
        st.warning("No valid images available for gallery")
        return
    st.markdown('### 🖼️ Gallery')
    cols = st.columns(4)
    for i, (_, p) in enumerate(projects.head(8).iterrows()):
        col = cols[i % 4]
        with col:
            try:
                st.image(p['Image'], caption=p['Project_Name'], use_container_width=True)
            except Exception as e:
                st.warning(f"Failed to load image for {p['Project_Name']}: {str(e)}")
            if pd.notna(p.get('Blog_Link')):
                st.markdown(f"[📖 See More]({p['Blog_Link']})")

# Main
def main():
    st.title("Kronos GMT - Project Dashboard")

    df = load_data()
    if df is None or df.empty:
        st.error("No data loaded")
        return

    service_options = create_service_mapping(df)

    with st.sidebar:
        st.markdown("### Filters")
        types = ["All"] + sorted(df['Customer_Type'].dropna().unique().tolist())
        selected_type = st.selectbox("🏢 Type", types, index=0)
        services = ["All"] + service_options if service_options else ["All"]
        selected_service = st.selectbox("🌎 Service", services, index=0)
        use_bounds_filter = st.checkbox("Filter by map bounds", value=False)
        st.button("Reset Filters", on_click=lambda: st.rerun())

    filtered_df = filter_data(df, selected_type, selected_service)

    # Initialize session state for map
    if 'map_center' not in st.session_state:
        st.session_state.map_center = [filtered_df['Latitude'].mean(), filtered_df['Longitude'].mean()] if not filtered_df.empty else [0, 0]
    if 'map_zoom' not in st.session_state:
        st.session_state.map_zoom = 8

    col1, col2 = st.columns([2, 1])

    # --- MAPA CON ESTADO PERSISTENTE ---
    with col1:
        st.markdown('<div class="section-header">📍 Project Location</div>', unsafe_allow_html=True)

        # Solo recrear el mapa si los filtros cambian, no en cada interacción del mapa
        map_key = f"map_{selected_type}_{selected_service}"
        if map_key not in st.session_state:
            st.session_state[map_key] = create_interactive_map(filtered_df)

        map_obj = st.session_state[map_key]

        if map_obj:
            map_data = st_folium(
                map_obj,
                key=f"folium_{map_key}",
                use_container_width=True,
                height=500,
                returned_objects=["bounds"],
                # Wait for interaction
                sticky=True,  # Mantiene el zoom/posición
            )
        else:
            map_data = {}

    with col2:
        st.markdown('<div class="section-header">📊 Services Provided</div>', unsafe_allow_html=True)

    # --- FILTRO ESPACIAL: Usar bounds del mapa ---
    displayed_df = filtered_df.copy()

    # Mostrar bounds para depuración (opcional, luego puedes quitarlo)
    # st.write("Debug - Map Data:", map_data)

    if map_data and 'bounds' in map_data and map_data['bounds']:
        try:
            bounds = map_data['bounds']
            sw = bounds['southWest']
            ne = bounds['northEast']

            displayed_df = filtered_df[
                (filtered_df['Latitude'] >= sw['lat']) &
                (filtered_df['Latitude'] <= ne['lat']) &
                (filtered_df['Longitude'] >= sw['lng']) &
                (filtered_df['Longitude'] <= ne['lng'])
            ]

            st.write(f"✅ **{len(displayed_df)} projects within current map view**")
        except Exception as e:
            st.warning(f"❌ Error in spatial filter: {e}")
    else:
        st.write("🔍 **Pan or zoom the map to filter projects by area**")

    # Actualizar gráfico
    with col2:
        chart = create_service_distribution(displayed_df)
        if chart is not None:
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.write("No service data in current view.")

    # Actualizar galería
    display_project_gallery(displayed_df)

    st.caption("© 2025 Kronos GMT")

if __name__ == "__main__":
    main()
