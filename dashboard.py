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

# Page configuration
st.set_page_config(
    page_title="Kronos GMT Project's Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown(""" ... (tu CSS original aquí) ... """, unsafe_allow_html=True)

def get_project_type_colors(customer_types):
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    valid_types = [t for t in customer_types if pd.notna(t)]
    return {t: colors[i % len(colors)] for i, t in enumerate(valid_types)}

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

def filter_data(df, project_type_filter, service_filter, bounds=None):
    filtered_df = df.copy()
    if project_type_filter != "All":
        filtered_df = filtered_df[filtered_df['Customer_Type'] == project_type_filter]
    if service_filter != "All":
        filtered_df = filtered_df[filtered_df['Service_2_list'].apply(lambda x: service_filter in x)]
    if bounds:
        lat_min, lat_max = bounds['_southWest']['lat'], bounds['_northEast']['lat']
        lng_min, lng_max = bounds['_southWest']['lng'], bounds['_northEast']['lng']
        filtered_df = filtered_df[
            (filtered_df['Latitude'].between(lat_min, lat_max)) &
            (filtered_df['Longitude'].between(lng_min, lng_max))
        ]
    return filtered_df

@st.cache_resource
def create_interactive_map(df, map_key):
    if df.empty:
        return None
    if 'Customer_Type' not in df.columns:
        df['Customer_Type'] = 'Unknown'
    df = df.dropna(subset=['Latitude', 'Longitude'])
    unique_types = df['Customer_Type'].dropna().unique()
    color_map = get_project_type_colors(unique_types)
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
    fig.update_layout(paper_bgcolor='#1a242e')
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

def create_navigation_sidebar():
    with st.sidebar:
        st.markdown("... (tu código original de sidebar aquí) ...", unsafe_allow_html=True)

def main():
    st.markdown('<h1 class="main-header"> Kronos GMT - Project Dashboard</h1>', unsafe_allow_html=True)
    df = load_data()
    if df is None or df.empty:
        st.stop()
    service_options = create_service_mapping(df)
    with st.sidebar:
        st.markdown("### Filters")
        types = ["All"] + sorted(df['Customer_Type'].dropna().unique().tolist())
        selected_type = st.selectbox("🏢 Type", types, index=0)
        services = ["All"] + service_options if service_options else ["All"]
        selected_service = st.selectbox("🌎 Service", services, index=0)
        st.button("Reset Filters", on_click=lambda: st.rerun())
        st.markdown("---")

    if 'map_bounds' not in st.session_state:
        st.session_state['map_bounds'] = None

    filtered_df = filter_data(df, selected_type, selected_service, bounds=st.session_state.get('map_bounds'))

    if filtered_df.empty:
        st.error("No projects match filters.")
    else:
        st.write(f"Showing {len(filtered_df)} projects")

    create_navigation_sidebar()

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown('<div class="section-header">📍 Project Location</div>', unsafe_allow_html=True)
        map_obj = create_interactive_map(filtered_df, "main_map")
        if map_obj:
            map_data = st_folium(map_obj, use_container_width=True, height=500)
            if map_data and "bounds" in map_data and map_data["bounds"]:
                if map_data["bounds"] != st.session_state.get('map_bounds'):
                    st.session_state['map_bounds'] = map_data["bounds"]
                    st.rerun()

    with col2:
        st.markdown('<div class="section-header">📊 Services Provided</div>', unsafe_allow_html=True)
        chart = create_service_distribution(filtered_df)
        if chart:
            st.plotly_chart(chart, use_container_width=True)

    display_project_gallery(filtered_df)

if __name__ == "__main__":
    main()
