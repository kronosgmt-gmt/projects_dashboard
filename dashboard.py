import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from urllib.parse import urlparse
import os
import requests
import io

# Cloudinary configuration
CLOUDINARY_CLOUD_NAME = "dmbgxvfo0"

# Page configuration
st.set_page_config(
    page_title="Kronos GMT Project's Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1f77b4; text-align: center; margin-bottom: 2rem; }
    .metric-card { background-color: #93c47d; padding: 1rem; border-radius: 10px; border-left: 5px solid #1f77b4; margin-bottom: 1rem; }
    .filter-section { background-color: #ffffff; padding: 1rem; border-radius: 10px; margin-bottom: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .stSelectbox > label { font-weight: bold; color: #1f77b4; }
    .section-header { font-size: 1.5rem; font-weight: bold; color: #2c3e50; margin: 1rem 0; border-bottom: 2px solid #1f77b4; padding-bottom: 0.5rem; }
    .cloudinary-image { max-width: 20vw; height: auto; object-fit: cover; border-radius: 5px; cursor: pointer; }
</style>
""", unsafe_allow_html=True)


def get_project_type_colors(customer_types):
    """Generate color mapping for project types."""
    colors = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
    ]
    # Remove NaN and convert to list
    valid_types = [t for t in customer_types if pd.notna(t)]
    return {t: colors[i % len(colors)] for i, t in enumerate(valid_types)}


def is_valid_cloudinary_url(url, cloud_name=None):
    if not url or pd.isna(url) or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    if cloud_name:
        return (parsed.netloc == "res.cloudinary.com" and
                url.startswith(f"https://res.cloudinary.com/{cloud_name}/"))
    return parsed.netloc == "res.cloudinary.com"


def load_data_from_url(url):
    try:
        if "github.com" in url:
            url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        content = io.StringIO(response.text)
        df = pd.read_csv(content, encoding='utf-8')
        #st.success(f"✅ Loaded data from URL: {url}")
        return df
    except Exception as e:
        st.warning(f"⚠️ Failed to load from URL: {str(e)}")
        return None


@st.cache_data
def load_data_from_csv(file_path):
    df = None
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
            #st.success("✅ Loaded data from local file")
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding='latin1')
            #st.success("✅ Loaded data from local file (latin1)")

    if df is None:
        urls = ["https://github.com/kronosgmt-gmt/projects_dashboard/blob/main/proyects.csv"]
        for url in urls:
            st.info(f"Trying GitHub: {url}")
            df = load_data_from_url(url)
            if df is not None:
                break

    if df is None:
        st.error("❌ Failed to load data.")
        return None

    # Clean columns
    df.columns = df.columns.str.strip()
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')

    # Clean Customer_Type
    if 'Customer_Type' in df.columns:
        df['Customer_Type'] = df['Customer_Type'].fillna('Unknown')
    else:
        df['Customer_Type'] = 'Unknown'

    # Clean Service_2
    def clean_services(x):
        if pd.isna(x) or not x:
            return []
        try:
            if isinstance(x, str):
                if x.startswith('['):
                    return [s.strip(" '") for s in x.strip("[]").split(',') if s.strip()]
                return [s.strip() for s in x.split(',') if s.strip()]
            return []
        except:
            return []

    if 'Service_2' in df.columns:
        df['Service_2_list'] = df['Service_2'].apply(clean_services)
    else:
        df['Service_2_list'] = [[] for _ in range(len(df))]

    # Validate required columns
    required = ['project_id', 'Project_Name', 'Longitude', 'Latitude']
    missing = [col for col in required if col not in df.columns]
    if missing:
        st.error(f"❌ Missing columns: {missing}")
        return None

    # Drop rows with invalid coordinates
    df.dropna(subset=['Longitude', 'Latitude'], inplace=True)
    df = df[(df['Latitude'].between(-90, 90)) & (df['Longitude'].between(-180, 180))]

    if 'Image' in df.columns and CLOUDINARY_CLOUD_NAME:
        df['Image'] = df['Image'].apply(
            lambda x: f"https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/image/upload/{x.strip()}"
            if pd.notna(x) and isinstance(x, str) and x.strip() and not is_valid_cloudinary_url(x, CLOUDINARY_CLOUD_NAME)
            else x
        )

    if df.empty:
        st.error("❌ No valid projects with coordinates.")
        return None

    return df


def create_service_mapping(df):
    all_services = set()
    for services in df['Service_2_list']:
        if isinstance(services, list):
            all_services.update(services)
    return sorted([s for s in all_services if s])


def filter_data(df, project_type_filter, service_filter):
    filtered_df = df.copy()
    if project_type_filter != "All":
        filtered_df = filtered_df[filtered_df['Customer_Type'] == project_type_filter]
    if service_filter != "All":
        filtered_df = filtered_df[filtered_df['Service_2_list'].apply(lambda x: service_filter in x)]
    return filtered_df


#los KPI estaban aqui y fueron eliminados

@st.cache_resource
def create_interactive_map(df):
    if df.empty or len(df) == 0:
        st.warning("No data to display on map.")
        return None

    # Ensure Customer_Type exists and is clean
    if 'Customer_Type' not in df.columns:
        df['Customer_Type'] = 'Unknown'

    # Remove rows with NaN coordinates
    df = df.dropna(subset=['Latitude', 'Longitude'])
    if df.empty:
        st.warning("No valid coordinates for mapping.")
        return None

    # Create color map
    unique_types = df['Customer_Type'].dropna().unique()
    color_map = get_project_type_colors(unique_types)

    # Center map
    center_lat = df['Latitude'].mean()
    center_lon = df['Longitude'].mean()

    m = folium.Map(location=[center_lat, center_lon], zoom_start=6)

    for _, row in df.iterrows():
        popup = f"<b>{row['Project_Name']}</b><br>Type: {row['Customer_Type']}"
        color = color_map.get(row['Customer_Type'], '#888888')

        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=8,
            popup=popup,
            tooltip=row['Project_Name'],
            fillColor=color,
            fillOpacity=0.7,
            color='white',
            weight=1
        ).add_to(m)

    # Add legend
    legend_html = '<div style="position: fixed; bottom: 50px; left: 50px; width: 180px; background: white; border: 2px solid grey; z-index: 9999; padding: 10px; border-radius: 5px;">'
    legend_html += '<p><b>Legend</b></p>'
    for t, c in color_map.items():
        legend_html += f'<p><i class="fa fa-circle" style="color:{c}"></i> {t}</p>'
    legend_html += '</div>'
    m.get_root().html.add_child(folium.Element(legend_html))

    return m


def create_service_distribution(df):
    if df.empty:
        return None
    all_services = [s for services in df['Service_2_list'] for s in services if s]
    if not all_services:
        return None
    counts = pd.Series(all_services).value_counts()
    fig = px.pie(values=counts.values, names=counts.index, title="Services")
    fig.update_traces(textinfo='percent+label')
    return fig


def display_project_gallery(df):
    if 'Image' not in df.columns:
        return
    projects = df[df['Image'].apply(lambda x: is_valid_cloudinary_url(x, CLOUDINARY_CLOUD_NAME))]
    if projects.empty:
        return
    st.markdown('<div class="section-header">🖼️ Gallery</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    for i, (_, p) in enumerate(projects.head(8).iterrows()):
        col = cols[i % 4]
        with col:
            st.image(p['Image'], caption=p['Project_Name'], use_container_width=True)
            if pd.notna(p.get('Blog_Link')):
                st.markdown(f"[📖 See More about this project]({p['Blog_Link']})")


def main():
    st.markdown('<h1 class="main-header"> Kronos GMT - Project Dashboard</h1>', unsafe_allow_html=True)

    df = load_data_from_csv("projects.csv")
    if df is None or df.empty:
        st.stop()

    #st.success(f"✅ Loaded {len(df)} projects")

    service_options = create_service_mapping(df)

    with st.sidebar:
        st.markdown('<div class="filter-section">', unsafe_allow_html=True)
        st.markdown("### 🎛️ Filters")
        types = ["All"] + sorted(df['Customer_Type'].dropna().unique().tolist())
        selected_type = st.selectbox("🏢 Type", types, index=0)
        services = ["All"] + service_options if service_options else ["All"]
        selected_service = st.selectbox("🔧 Service", services, index=0)
        st.button("Reset Filters", on_click=lambda: st.rerun())
        st.markdown('</div>', unsafe_allow_html=True)

    filtered_df = filter_data(df, selected_type, selected_service)

    if filtered_df.empty:
        st.error("No projects match filters.")
    else:
        st.write(f"Showing {len(filtered_df)} projects")

    #create_kpi_cards(filtered_df)

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown('<div class="section-header">📍 Map</div>', unsafe_allow_html=True)
        map_obj = create_interactive_map(filtered_df)
        if map_obj:
            st_folium(map_obj, use_container_width=True, height=500)

    with col2:
        st.markdown('<div class="section-header">📊 Services</div>', unsafe_allow_html=True)
        chart = create_service_distribution(filtered_df)
        if chart:
            st.plotly_chart(chart, use_container_width=True)

    display_project_gallery(filtered_df)

    st.markdown('<div class="section-header">📋 Projects</div>', unsafe_allow_html=True)
    if not filtered_df.empty:
        display_cols = ['Project_Name', 'Customer_Type', 'Service_2', 'Scope of work', 'year']
        available_cols = [c for c in display_cols if c in filtered_df.columns]
        st.dataframe(filtered_df[available_cols], use_container_width=True, hide_index=True)
    else:
        st.warning("No data to show")

    st.markdown("---")
    st.caption("© 2025 Kronos GMT | Created by Juan Cano")


if __name__ == "__main__":
    main()
