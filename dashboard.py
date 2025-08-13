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
import streamlit.components.v1 as components

# Cloudinary configuration
CLOUDINARY_CLOUD_NAME = "dmbgxvfo0"

# Page configuration with dark mode
st.set_page_config(
    page_title="Kronos GMT Project's Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS with dark mode
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; background-color: #1a252f; font-weight: bold; color: #ffffff; text-align: center; margin-bottom: 2rem; }
    .metric-card { background-color: #2c3e50; padding: 1rem; border-radius: 10px; border-left: 5px solid #07b9d1; margin-bottom: 1rem; }
    .filter-section { background-color: #34495e; padding: 1rem; border-radius: 10px; margin-bottom: 1rem; }
    .stSelectbox > label { font-weight: bold; color: #ffffff; }
    .section-header { font-size: 1.5rem; font-weight: bold; color: #ffffff; margin: 1rem 0; border-bottom: 2px solid #07b9d1; padding-bottom: 0.5rem; }
    .cloudinary-image { max-width: 20vw; height: auto; object-fit: cover; border-radius: 5px; cursor: pointer; }
    .nav-button {
        display: block;
        width: 100%;
        padding: 10px;
        margin: 5px 0;
        background-color: #34495e;
        color: #ffffff;
        text-decoration: none;
        border-radius: 5px;
        text-align: center;
        border: none;
        cursor: pointer;
        font-size: 14px;
        font-weight: bold;
        text-decoration: none;
    }
    .nav-button:hover {
        background-color: #2c3e50;
        font-weight: bold;
        color: #1a252f;
        text-decoration: none;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
    }
    .logo-container {
        text-align: center;
        margin-bottom: 20px;
    }
    .stApp {
        background-color: #1a252f;
    }

    /* Neon effect for Services expander */
    @keyframes neonPulse {
        0% { box-shadow: 0 0 5px #00FFFF, 0 0 10px #00FFFF; border-color: #00FFFF; }
        25% { box-shadow: 0 0 10px #00CCFF, 0 0 20px #00CCFF; border-color: #00CCFF; }
        50% { box-shadow: 0 0 20px #0099FF, 0 0 30px #0099FF; border-color: #0099FF; }
        75% { box-shadow: 0 0 10px #00CCFF, 0 0 20px #00CCFF; border-color: #00CCFF; }
        100% { box-shadow: 0 0 5px #00FFFF, 0 0 10px #00FFFF; border-color: #00FFFF; }
    }
    div[data-testid="stExpander"] summary {
        animation: neonPulse 2s infinite;
        border: 2px solid #00FFFF;
        border-radius: 8px;
        background: linear-gradient(135deg, #1a2332 0%, #2c3e50 100%);
        padding: 12px;
        font-weight: bold;
        text-transform: uppercase;
        color: #00FFFF;
        letter-spacing: 1px;
        text-shadow: 0 0 5px rgba(113, 217, 11, 0.5);
    }
</style>
""", unsafe_allow_html=True)


def is_valid_cloudinary_url(url, cloud_name=None):
    if not url or pd.isna(url) or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    if cloud_name:
        return (parsed.netloc == "res.cloudinary.com" and url.startswith(f"https://res.cloudinary.com/{cloud_name}/"))
    return parsed.netloc == "res.cloudinary.com"


@st.cache_data
def load_data():
    url = "https://github.com/kronosgmt-gmt/projects_dashboard/blob/main/proyects.csv"
    try:
        if "github.com" in url:
            url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        content = io.StringIO(response.text)
        df = pd.read_csv(content, encoding='utf-8')

        # Data cleaning and validation
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

        required = ['project_id', 'Project_Name', 'Longitude', 'Latitude']
        missing = [col for col in required if col not in df.columns]
        if missing:
            st.error(f"❌ Missing columns: {missing}")
            return None

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
    except Exception as e:
        st.warning(f"⚠️ Failed to load from URL: {str(e)}")
        return None


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


@st.cache_resource
def get_project_type_colors(customer_types):
    """Define colors for different project types"""
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    valid_types = [t for t in customer_types if pd.notna(t)]
    return {t: colors[i % len(colors)] for i, t in enumerate(valid_types)}


def create_simple_map(df):
    """Map with color coding by project type (no spatial filtering)"""
    if df.empty or len(df) == 0:
        st.warning("No data to display on map.")
        return None

    if 'Customer_Type' not in df.columns:
        df['Customer_Type'] = 'Unknown'

    df = df.dropna(subset=['Latitude', 'Longitude'])
    if df.empty:
        st.warning("No valid coordinates for mapping.")
        return None

    # Get unique types and assign colors
    unique_types = df['Customer_Type'].dropna().unique()
    color_map = get_project_type_colors(unique_types)

    center_lat = df['Latitude'].mean()
    center_lon = df['Longitude'].mean()

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=6,
        tiles="OpenStreetMap"
    )
    
    for _, row in enumerate(df.iterrows()):
        _, row = row
        popup = f"<b>{row['Project_Name']}</b><br>Type: {row['Customer_Type']}"
        
        # Use color based on Customer_Type
        color = color_map.get(row['Customer_Type'], '#888888')

        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=8,
            popup=popup,
            tooltip=row['Project_Name'],
            fillColor=color,
            fillOpacity=0.8,
            color='white',
            weight=2
        ).add_to(m)

    # Add simple legend
    legend_html = '''
    <div style="position: fixed; bottom: 50px; left: 50px; width: 180px; background: #1a252f; 
                border: 2px solid #07b9d1; z-index: 9999; padding: 10px; border-radius: 5px; font-size: 14px;">
        <p style="color: white; margin: 0 0 5px 0;"><b>Project Types</b></p>
    '''
    for project_type, color in color_map.items():
        legend_html += f'<p style="margin: 3px 0; color: white;"><i class="fa fa-circle" style="color:{color}; margin-right: 8px;"></i> {project_type}</p>'
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
    fig = px.pie(values=counts.values, names=counts.index, title="Services Distribution")
    fig.update_traces(textinfo='percent+label')
    fig.update_layout(
        paper_bgcolor='#1a242e',
        plot_bgcolor='#1a242e',
        font_color="white",
        title_font_size=16
    )
    return fig


def display_project_gallery(df):
    if 'Image' not in df.columns:
        return
    projects = df[df['Image'].apply(lambda x: is_valid_cloudinary_url(x, CLOUDINARY_CLOUD_NAME))]
    if projects.empty:
        st.write("No images available.")
        return
    st.markdown('<div class="section-header">🖼️ Project Gallery</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    for i, (_, p) in enumerate(projects.head(8).iterrows()):
        col = cols[i % 4]
        with col:
            st.image(p['Image'], caption=p['Project_Name'], use_container_width=True)
            if pd.notna(p.get('Blog_Link')):
                st.markdown(f"[📖 Learn More]({p['Blog_Link']})", unsafe_allow_html=True)


def create_navigation_sidebar():
    with st.sidebar:
        st.markdown("""
        <div class="logo-container">
            <a href="https://kronosgmt.com" target="_blank">
                <img src="https://res.cloudinary.com/dmbgxvfo0/image/upload/v1754540320/Logos_Kronos_PNG-04_nxdbz3.png" 
                     style="width: 300px; height: auto; border-radius: 10px; cursor: pointer;">
            </a>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("Services", expanded=False):
            st.markdown("""<a href="https://www.kronosgmt.com/3D-rendering" target="_blank" class="nav-button">3D Rendering</a>""", unsafe_allow_html=True)
            st.markdown("""<a href="https://www.kronosgmt.com/CAD-drafting" target="_blank" class="nav-button">CAD Drafting</a>""", unsafe_allow_html=True)
            st.markdown("""<a href="https://www.kronosgmt.com/takeoffs-schedules" target="_blank" class="nav-button">Takeoffs & Schedules</a>""", unsafe_allow_html=True)
            st.markdown("""<a href="https://www.kronosgmt.com/GIS-mapping" target="_blank" class="nav-button">GIS Mapping</a>""", unsafe_allow_html=True)
            st.markdown("""<a href="https://www.kronosgmt.com/automation-workflow-optimization" target="_blank" class="nav-button">Automation & Workflow Optimization</a>""", unsafe_allow_html=True)

        st.markdown("""<a href="https://news.kronosgmt.com/" target="_blank" class="nav-button">News</a>""", unsafe_allow_html=True)
        st.markdown("""<a href="https://www.kronosgmt.com/#contact" target="_blank" class="nav-button">Contact Us</a>""", unsafe_allow_html=True)
        st.markdown("---")


def main():
    st.markdown('<h1 class="main-header">Kronos GMT - Project Dashboard</h1>', unsafe_allow_html=True)

    df = load_data()
    if df is None or df.empty:
        st.error("❌ No data loaded. Check your data source.")
        st.stop()

    service_options = create_service_mapping(df)

    # Sidebar filters
    with st.sidebar:
        st.markdown("### 🔍 Filters")
        types = ["All"] + sorted(df['Customer_Type'].dropna().unique().tolist())
        selected_type = st.selectbox("🏢 Project Type", types, index=0)
        services = ["All"] + service_options if service_options else ["All"]
        selected_service = st.selectbox("🌎 Service", services, index=0)
        
        st.markdown("---")

    # Apply filters
    filtered_df = filter_data(df, selected_type, selected_service)

    if filtered_df.empty:
        st.error("❌ No projects match the selected filters.")
        st.stop()

    create_navigation_sidebar()

    # Show statistics
    st.markdown(f"📊 **Showing {len(filtered_df)} of {len(df)} total projects**")

    # Layout
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown('<div class="section-header">📍 Project Locations</div>', unsafe_allow_html=True)
        map_obj = create_simple_map(filtered_df)
        if map_obj is not None:
            st_folium(map_obj, use_container_width=True, height=500)
        else:
            st.warning("⚠️ Map could not be generated.")

    with col2:
        st.markdown('<div class="section-header">📊 Services Overview</div>', unsafe_allow_html=True)
        # Use filtered_df (by type and service filters) not displayed_df (spatial filter)
        chart = create_service_distribution(filtered_df)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.write("No service data available for selected filters.")

    # Project gallery - uses filtered data (by type/service), not spatial filtering
    display_project_gallery(filtered_df)

    st.markdown("---")
    st.caption("© 2025 Kronos GMT | Dashboard by Juan Cano")


if __name__ == "__main__":
    main()
