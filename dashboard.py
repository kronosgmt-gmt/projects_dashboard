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

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #93c47d;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin-bottom: 1rem;
    }
    .filter-section {
        background-color: #ffffff;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stSelectbox > label {
        font-weight: bold;
        color: #1f77b4;
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2c3e50;
        margin: 1rem 0;
        border-bottom: 2px solid #1f77b4;
        padding-bottom: 0.5rem;
    }
    .cloudinary-image {
        max-width: 20vw;
        height: auto;
        object-fit: cover;
        border-radius: 5px;
        cursor: pointer;
    }
</style>
""", unsafe_allow_html=True)


def get_project_type_colors(customer_types):
    """Generate color mapping for project types."""
    colors = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
        '#ff9999', '#66b3ff', '#99ff99', '#ffcc99', '#ff99cc'
    ]
    return {customer_type: colors[i % len(colors)] for i, customer_type in enumerate(customer_types)}


def is_valid_cloudinary_url(url, cloud_name=None):
    """Validate if a URL is a valid Cloudinary URL."""
    if not url or pd.isna(url):
        return False
    parsed = urlparse(url)
    if cloud_name:
        return (parsed.netloc == "res.cloudinary.com" and
                url.startswith(f"https://res.cloudinary.com/{cloud_name}/") and
                parsed.scheme in ["http", "https"])
    return parsed.netloc == "res.cloudinary.com" and parsed.scheme in ["http", "https"]


def load_data_from_url(url):
    """Load data from GitHub URL."""
    try:
        if "github.com" in url and "raw.githubusercontent.com" not in url:
            url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        content = io.StringIO(response.text)
        df = pd.read_csv(content, encoding='utf-8')
        st.success(f"✅ Loaded data from URL: {url}")
        return df
    except Exception as e:
        st.warning(f"⚠️ Failed to load from URL {url}: {str(e)}")
        return None


@st.cache_data
def load_data_from_csv(file_path):
    """Load and prepare data from local CSV file or GitHub URL."""
    df = None
    # Try local file first
    if os.path.exists(file_path):
        try:
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
                st.success("✅ Loaded data from local file")
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='latin1')
                st.success("✅ Loaded data from local file (latin1 encoding)")
        except Exception as e:
            st.warning(f"⚠️ Could not load local file: {str(e)}")

    # Try GitHub URLs if local file fails
    if df is None:
        github_urls = [
            "https://raw.githubusercontent.com/kronosgmt-gmt/projects_dashboard/main/data/projects.csv",
        ]
        for url in github_urls:
            st.info(f"Trying to load from: {url}")
            df = load_data_from_url(url)
            if df is not None:
                break

    if df is None:
        st.error("❌ Failed to load data from local file or GitHub URLs.")
        return None

    # Data cleaning and validation
    try:
        df.columns = df.columns.str.strip()

        if 'start_date' in df.columns:
            df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce')
        if 'year' not in df.columns and 'start_date' in df.columns:
            df['year'] = df['start_date'].dt.year

        def clean_services(service_str):
            if pd.isna(service_str) or service_str == '':
                return []
            try:
                service_str = str(service_str)
                if service_str.startswith('[') and service_str.endswith(']'):
                    cleaned = service_str.strip('[]').replace('"', '').replace("'", "")
                    return [s.strip() for s in cleaned.split(',') if s.strip()]
                return [s.strip() for s in service_str.split(',') if s.strip()]
            except:
                return [service_str.strip()] if service_str.strip() else []

        if 'Service_2' in df.columns:
            df['Service_2_list'] = df['Service_2'].apply(clean_services)
        else:
            df['Service_2_list'] = [[] for _ in range(len(df))]

        required_columns = ['project_id', 'Project_Name', 'Longitude', 'Latitude', 'Customer_Type']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.error(f"❌ Missing required columns: {missing_columns}")
            return None

        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df = df.dropna(subset=['Longitude', 'Latitude'])
        df = df[(df['Latitude'].between(-90, 90)) & (df['Longitude'].between(-180, 180))]

        if 'Image' in df.columns and CLOUDINARY_CLOUD_NAME:
            df['Image'] = df['Image'].apply(
                lambda x: f"https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/image/upload/{x}"
                if pd.notna(x) and x.strip() and not is_valid_cloudinary_url(x, CLOUDINARY_CLOUD_NAME)
                else x
            )

        if df.empty:
            st.error("❌ No projects with valid coordinates.")
            return None

        st.write(f"Loaded {len(df)} projects. Sample: {df[['Project_Name', 'Latitude', 'Longitude']].head(2).to_dict('records')}")
        if 'Image' in df.columns:
            valid_images = df['Image'].apply(lambda x: is_valid_cloudinary_url(x, CLOUDINARY_CLOUD_NAME)).sum()
            st.write(f"Found {valid_images} valid Cloudinary images out of {len(df)} projects.")

        return df
    except Exception as e:
        st.error(f"❌ Error processing data: {str(e)}")
        return None


def create_service_mapping(df):
    """Create mapping for services from the data."""
    all_services = set()
    for services in df['Service_2_list']:
        all_services.update(services)
    all_services.discard('')
    return sorted(list(all_services))


def filter_data(df, project_type_filter, service_filter):
    """Filter dataframe based on selected filters."""
    filtered_df = df.copy()
    if project_type_filter != "All":
        filtered_df = filtered_df[filtered_df['Customer_Type'] == project_type_filter]
    if service_filter != "All":
        filtered_df = filtered_df[filtered_df['Service_2_list'].apply(lambda x: service_filter in x)]
    return filtered_df


def create_kpi_cards(df):
    """Create KPI cards."""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h3>📊 Total Projects</h3>
            <h2>{len(df)}</h2>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        if 'Status' in df.columns:
            completed_projects = len(df[df['Status'].str.contains('Done|Complete', case=False, na=False)])
        else:
            completed_projects = 0
        st.markdown(f"""
        <div class="metric-card">
            <h3>✅ Completed</h3>
            <h2>{completed_projects}</h2>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        unique_clients = df['Client'].nunique() if 'Client' in df.columns else 0
        st.markdown(f"""
        <div class="metric-card">
            <h3>🏢 Clients</h3>
            <h2>{unique_clients}</h2>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        current_year = datetime.now().year
        current_year_projects = len(df[df['year'] == current_year]) if 'year' in df.columns else 0
        st.markdown(f"""
        <div class="metric-card">
            <h3>📅 This Year</h3>
            <h2>{current_year_projects}</h2>
        </div>
        """, unsafe_allow_html=True)


@st.cache_resource
def create_interactive_map(df):
    """Create interactive map with project locations."""
    if df.empty:
        st.warning("No project locations available for the selected filters. Try setting filters to 'All'.")
        return None

    # Validar que la columna Customer_Type exista
    if 'Customer_Type' not in df.columns:
        st.error("The column 'Customer_Type' is missing in the data.")
        return None

    df = df[df['Latitude'].between(-90, 90) & df['Longitude'].between(-180, 180)]
    if df.empty:
        st.warning("No projects with valid coordinates (Latitude: -90 to 90, Longitude: -180 to 180).")
        return None

    st.info(f"Plotting {len(df)} projects on the map. Sample: {df[['Project_Name', 'Latitude', 'Longitude']].head(2).to_dict('records')}")

    center_lat = df['Latitude'].mean()
    center_lon = df['Longitude'].mean()
    if pd.isna(center_lat) or pd.isna(center_lon):
        center_lat, center_lon = 0, 0
        st.warning("Using default map center (0, 0). Check coordinate data.")

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=10,
        tiles='OpenStreetMap'
    )

    marker_cluster = MarkerCluster().add_to(m)
    placeholder_image = "https://via.placeholder.com/150x90"

    # Generar color_map
    try:
        color_map = get_project_type_colors(df['Customer_Type'].unique())
    except Exception as e:
        st.error(f"Failed to generate color_map: {str(e)}")
        return None

    for idx, row in df.iterrows():
        if pd.isna(row['Latitude']) or pd.isna(row['Longitude']):
            continue

        popup_content = f"""
            <div style="width: 300px;">
                <h4><b>{row['Project_Name']}</b></h4>
                <p><b>Type:</b> {row['Customer_Type']}</p>
        """

        if 'Client' in df.columns and pd.notna(row['Client']):
            popup_content += f"<p><b>Client:</b> {row['Client']}</p>"
        if 'year' in df.columns and pd.notna(row['year']):
            popup_content += f"<p><b>Year:</b> {int(row['year'])}</p>"
        if 'Department' in df.columns and pd.notna(row['Department']):
            popup_content += f"<p><b>Department:</b> {row['Department']}</p>"
        if 'Image' in df.columns and pd.notna(row['Image']) and str(row['Image']).strip():
            image_url = row['Image'] if is_valid_cloudinary_url(row['Image'], CLOUDINARY_CLOUD_NAME) else placeholder_image
            popup_content += f"""
                <div style="margin-top: 10px;">
                    <img src="{image_url}" class="cloudinary-image" alt="Project Image" 
                         style="max-width: 20vw; height: auto; border-radius: 5px;">
                </div>
            """
        if 'Blog_Link' in df.columns and pd.notna(row['Blog_Link']) and str(row['Blog_Link']).strip():
            popup_content += f"""
                <div style="margin-top: 10px;">
                    <a href="{row['Blog_Link']}" target="_blank" style="color: #1f77b4;">
                        📖 Read Blog Post
                    </a>
                </div>
            """
        popup_content += "</div>"

        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=8,
            popup=folium.Popup(popup_content, max_width=350),
            tooltip=row['Project_Name'],
            color='white',
            weight=2,
            fillColor=color_map.get(row['Customer_Type'], '#gray'),
            fillOpacity=0.7
        ).add_to(marker_cluster)

    legend_items = ''.join([
        f'<p><i class="fa fa-circle" style="color:{color}"></i> {type_name}</p>'
        for type_name, color in color_map.items()
    ])
    legend_html = f'''
    <div style="position: absolute; 
                bottom: 5%; left: 5%; width: 200px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px; border-radius: 5px;">
    <p><b>Project Types</b></p>
    {legend_items}
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    return m


def create_service_distribution(df):
    """Create service distribution pie chart."""
    if df.empty:
        st.warning("No service data available for the selected filters.")
        return None
    all_services = []
    for services in df['Service_2_list']:
        all_services.extend(services)
    if not all_services:
        st.warning("No service data available.")
        return None
    service_counts = pd.Series(all_services).value_counts()
    fig = px.pie(
        values=service_counts.values,
        names=service_counts.index,
        title='Service Distribution'
    )
    fig.update_traces(textposition='inside', textinfo='percent+label')
    return fig


def display_project_gallery(df):
    """Display project gallery with Cloudinary images."""
    if df.empty or 'Image' not in df.columns:
        st.warning("No project images available for the selected filters.")
        return
    projects_with_images = df[df['Image'].notna() & (df['Image'].str.strip() != '')]
    if projects_with_images.empty:
        st.info("No project images available for the current filters.")
        return
    st.markdown('<div class="section-header">🖼️ Project Gallery</div>', unsafe_allow_html=True)
    placeholder_image = "https://via.placeholder.com/150x90"
    cols = st.columns(4)
    for idx, (_, project) in enumerate(projects_with_images.head(12).iterrows()):
        col_idx = idx % 4
        with cols[col_idx]:
            with st.container():
                image_url = project['Image'] if is_valid_cloudinary_url(project['Image'], CLOUDINARY_CLOUD_NAME) else placeholder_image
                st.image(image_url, caption=project['Project_Name'], use_container_width=True)
                if 'Blog_Link' in df.columns and pd.notna(project['Blog_Link']) and project['Blog_Link'].strip():
                    st.markdown(f"[📖 Read More]({project['Blog_Link']})")


def main():
    st.markdown('<h1 class="main-header">📊 Kronos GMT - Project Dashboard</h1>', unsafe_allow_html=True)
    csv_file_path = "projects.csv"
    github_url = st.text_input("Or enter GitHub raw CSV URL:", placeholder="https://raw.githubusercontent.com/.../projects.csv")

    with st.spinner("Loading data..."):
        if github_url:
            df = load_data_from_url(github_url)
        else:
            df = load_data_from_csv(csv_file_path)

    if df is None:
        st.error("❌ Failed to load data. Check the file path or URL.")
        return

    if df.empty:
        st.error("❌ The CSV file is empty or has no valid data.")
        return

    st.success(f"✅ Successfully loaded {len(df)} projects!")

    service_options = create_service_mapping(df)

    st.sidebar.markdown('<div class="filter-section">', unsafe_allow_html=True)
    st.sidebar.markdown("### 🎛️ Filters")
    project_types = ["All"] + sorted(df['Customer_Type'].unique().tolist())
    selected_project_type = st.sidebar.selectbox(
        "🏢 Project Type",
        options=project_types,
        index=0,
        help="Filter projects by type"
    )

    if service_options:
        service_options_with_all = ["All"] + service_options
        selected_service = st.sidebar.selectbox(
            "🔧 Service",
            options=service_options_with_all,
            index=0,
            help="Filter projects by service type"
        )
    else:
        selected_service = "All"
        st.sidebar.info("No service data available")

    if st.sidebar.button("Reset Filters"):
        st.rerun()

    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Data Summary")
    st.sidebar.metric("Total Projects", len(df))
    st.sidebar.metric("Project Types", df['Customer_Type'].nunique())
    if service_options:
        st.sidebar.metric("Available Services", len(service_options))

    filtered_df = filter_data(df, selected_project_type, selected_service)

    if filtered_df.empty:
        st.error("No projects match the current filters. Try setting 'All' or check CSV data.")
    else:
        st.write(f"Filtered {len(filtered_df)} projects. Sample: {filtered_df[['Project_Name', 'Latitude', 'Longitude', 'Customer_Type']].head(2).to_dict('records')}")

    if selected_project_type != "All" or selected_service != "All":
        filter_info = []
        if selected_project_type != "All":
            filter_info.append(f"Project Type: **{selected_project_type}**")
        if selected_service != "All":
            filter_info.append(f"Service: **{selected_service}**")
        st.info(f"🔍 Active Filters: {' | '.join(filter_info)} | Showing {len(filtered_df)} of {len(df)} projects")

    create_kpi_cards(filtered_df)

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown('<div class="section-header">📍 Project Locations</div>', unsafe_allow_html=True)
        map_obj = create_interactive_map(filtered_df)
        if map_obj:
            st_folium(map_obj, width=None, height=500, use_container_width=True)
            st.info("💡 Click on map markers to see project details, images, and blog links!")

    with col2:
        st.markdown('<div class="section-header">📊 Service Distribution</div>', unsafe_allow_html=True)
        service_chart = create_service_distribution(filtered_df)
        if service_chart:
            st.plotly_chart(service_chart, use_container_width=True)

    display_project_gallery(filtered_df)

    st.markdown('<div class="section-header">📋 Project Details</div>', unsafe_allow_html=True)
    if not filtered_df.empty:
        column_mapping = {
            'project_id': 'ID',
            'Project_Name': 'Project Name',
            'Customer_Type': 'Project Type',
            'Service_2': 'Services',
            'Scope of work': 'Scope of Work',
            'Client': 'Client',
            'Department': 'Department',
            'year': 'Year'
        }
        available_columns = [col for col in column_mapping.keys() if col in filtered_df.columns]
        table_df = filtered_df[available_columns].copy()
        table_df.columns = [column_mapping[col] for col in table_df.columns]
        search_term = st.text_input("🔍 Search projects:", placeholder="Enter project name, client, or keyword...")
        if search_term:
            search_cols = [col for col in ['Project Name', 'Client', 'Scope of Work'] if col in table_df.columns]
            mask = table_df[search_cols].astype(str).apply(
                lambda x: x.str.contains(search_term, case=False, na=False)
            ).any(axis=1)
            table_df = table_df[mask]

        page_size = 10
        total_rows = len(table_df)
        total_pages = max(1, (total_rows - 1) // page_size + 1)

        if total_pages > 1:
            page = st.selectbox("Page", range(1, total_pages + 1))
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            display_df = table_df.iloc[start_idx:end_idx]
        else:
            display_df = table_df

        column_config = {}
        for col in display_df.columns:
            if col == 'ID':
                column_config[col] = st.column_config.NumberColumn(col, width="small")
            elif col in ['Project Name', 'Scope of Work']:
                column_config[col] = st.column_config.TextColumn(col, width="large")
            elif col == 'Year':
                column_config[col] = st.column_config.NumberColumn(col, width="small")
            else:
                column_config[col] = st.column_config.TextColumn(col, width="medium")

        st.dataframe(display_df, use_container_width=True, hide_index=True, column_config=column_config)
        if total_pages > 1:
            st.caption(f"Showing {len(display_df)} of {total_rows} projects")
    else:
        st.warning("No projects match the current filter criteria.")

    st.markdown("---")
    st.markdown(
        f"""
        <div style='text-align: center; color: #666; padding: 20px;'>
            <p>📊 Project Dashboard | KRONOS GMT 2025</p>
            <p>Created by Juan Cano</p>
            <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
