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
    
    color_mapping = {}
    for i, customer_type in enumerate(customer_types):
        color_mapping[customer_type] = colors[i % len(colors)]
    
    return color_mapping

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
        # Convert GitHub URL to raw URL if needed
        if "github.com" in url and "raw.githubusercontent.com" not in url:
            url = url.replace("github.com", "raw.githubusercontent.com")
            url = url.replace("/blob/", "/")
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Save content to a temporary file and read with pandas
        import io
        content = io.StringIO(response.text)
        df = pd.read_csv(content, encoding='utf-8')
        return df
    except Exception as e:
        st.error(f"Error loading from URL: {str(e)}")
        return None

@st.cache_data
def load_data_from_csv(file_path):
    """Load and prepare data from local CSV file or GitHub URL."""
    df = None
    
    # Try to load from local file first
    if os.path.exists(file_path):
        try:
            # Try different encodings
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
                st.success("✅ Loaded data from local file")
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='latin1')
                st.success("✅ Loaded data from local file (latin1 encoding)")
        except Exception as e:
            st.warning(f"⚠️ Could not load local file: {str(e)}")
    
    # If local file doesn't exist or failed, try GitHub URLs
    if df is None:
        github_urls = [
            "https://raw.githubusercontent.com/your-username/your-repo/main/projectos.csv",
            "https://raw.githubusercontent.com/your-username/your-repo/master/projectos.csv"
        ]
        
        for url in github_urls:
            st.info(f"Trying to load from: {url}")
            df = load_data_from_url(url)
            if df is not None:
                st.success(f"✅ Loaded data from GitHub: {url}")
                break
    
    if df is None:
        st.error("❌ Could not load data from local file or GitHub URLs")
        return None
    
    try:
        # Clean column names
        df.columns = df.columns.str.strip()
        
        # Convert date columns
        if 'start_date' in df.columns:
            df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce')
        
        # Create year column if it doesn't exist
        if 'year' not in df.columns and 'start_date' in df.columns:
            df['year'] = df['start_date'].dt.year
        
        # Clean and normalize service data
        def clean_services(service_str):
            if pd.isna(service_str) or service_str == '':
                return []
            try:
                if str(service_str).startswith('[') and str(service_str).endswith(']'):
                    cleaned = str(service_str).strip('[]').replace('"', '').replace("'", "")
                    return [s.strip() for s in cleaned.split(',') if s.strip()]
                return [s.strip() for s in str(service_str).split(',') if s.strip()]
            except:
                return [str(service_str).strip()] if str(service_str).strip() else []
        
        if 'Service_2' in df.columns:
            df['Service_2_list'] = df['Service_2'].apply(clean_services)
        else:
            df['Service_2_list'] = [[] for _ in range(len(df))]
        
        # Ensure required columns exist
        required_columns = ['project_id', 'Project_Name', 'Longitude', 'Latitude', 'Customer_Type']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.error(f"❌ Missing required columns: {missing_columns}")
            return None
        
        # Convert coordinates to numeric
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        
        # Remove rows with invalid coordinates
        df = df.dropna(subset=['Longitude', 'Latitude'])
        
        # Filter valid coordinate ranges
        df = df[(df['Latitude'].between(-90, 90)) & (df['Longitude'].between(-180, 180))]
        
        # Debug: Show loaded data
        if df is not None and not df.empty:
            st.info(f"📊 Loaded {len(df)} projects with valid coordinates")
            # Show sample coordinates for debugging
            sample_coords = df[['Project_Name', 'Latitude', 'Longitude', 'Customer_Type']].head(3)
            with st.expander("🔍 Sample Data Preview"):
                st.dataframe(sample_coords)
        
        # Check Cloudinary images
        if 'Image' in df.columns:
            valid_images = df['Image'].apply(lambda x: is_valid_cloudinary_url(x, CLOUDINARY_CLOUD_NAME)).sum()
            st.info(f"🖼️ Found {valid_images} valid Cloudinary images out of {len(df)} projects")
        
        return df
    except Exception as e:
        st.error(f"❌ Error processing CSV data: {str(e)}")
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

def create_project_map(df):
    """Create interactive map with project locations - no caching."""
    if df.empty:
        st.warning("⚠️ No project locations available for the selected filters.")
        return None

    # Validate coordinates
    valid_df = df[df['Latitude'].between(-90, 90) & df['Longitude'].between(-180, 180)].copy()
    if valid_df.empty:
        st.warning("⚠️ No projects with valid coordinates found.")
        return None

    # Debug information
    st.info(f"🗺️ Creating map with {len(valid_df)} projects")
    
    # Create color mapping for project types
    unique_types = valid_df['Customer_Type'].unique()
    type_colors = get_project_type_colors(unique_types)
    
    # Calculate map center
    center_lat = valid_df['Latitude'].mean()
    center_lon = valid_df['Longitude'].mean()
    
    # Determine zoom level based on coordinate spread
    lat_range = valid_df['Latitude'].max() - valid_df['Latitude'].min()
    lon_range = valid_df['Longitude'].max() - valid_df['Longitude'].min()
    
    if lat_range < 0.01 and lon_range < 0.01:
        zoom_start = 15
    elif lat_range < 0.1 and lon_range < 0.1:
        zoom_start = 12
    elif lat_range < 1 and lon_range < 1:
        zoom_start = 10
    else:
        zoom_start = 6

    # Initialize map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_start,
        tiles='OpenStreetMap'
    )

    # Add marker clustering
    marker_cluster = MarkerCluster().add_to(m)
    placeholder_image = "https://via.placeholder.com/150x90?text=No+Image"

    # Add markers
    for idx, row in valid_df.iterrows():
        # Get color for this project type
        marker_color = type_colors.get(row['Customer_Type'], '#gray')
        
        # Create popup content
        popup_content = f"""
            <div style="width: 300px; font-family: Arial, sans-serif;">
                <h4 style="margin: 0 0 10px 0; color: #1f77b4;"><b>{row['Project_Name']}</b></h4>
                <p style="margin: 5px 0;"><b>Type:</b> {row['Customer_Type']}</p>
        """
        
        if 'Client' in df.columns and pd.notna(row['Client']):
            popup_content += f"<p style='margin: 5px 0;'><b>Client:</b> {row['Client']}</p>"
        if 'year' in df.columns and pd.notna(row['year']):
            popup_content += f"<p style='margin: 5px 0;'><b>Year:</b> {int(row['year'])}</p>"
        if 'Department' in df.columns and pd.notna(row['Department']):
            popup_content += f"<p style='margin: 5px 0;'><b>Department:</b> {row['Department']}</p>"
        
        if 'Image' in df.columns and pd.notna(row['Image']) and str(row['Image']).strip():
            image_url = row['Image'] if is_valid_cloudinary_url(row['Image'], CLOUDINARY_CLOUD_NAME) else placeholder_image
            popup_content += f"""
                <div style="margin-top: 10px; text-align: center;">
                    <img src="{image_url}" style="max-width: 280px; max-height: 150px; border-radius: 5px;" alt="Project Image">
                </div>
            """
        
        if 'Blog_Link' in df.columns and pd.notna(row['Blog_Link']) and str(row['Blog_Link']).strip():
            popup_content += f"""
                <div style="margin-top: 10px; text-align: center;">
                    <a href="{row['Blog_Link']}" target="_blank" style="color: #1f77b4; text-decoration: none;">
                        📖 Read Blog Post
                    </a>
                </div>
            """
        
        popup_content += "</div>"

        # Add marker
        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=8,
            popup=folium.Popup(popup_content, max_width=350),
            tooltip=f"{row['Project_Name']} ({row['Customer_Type']})",
            color='white',
            weight=2,
            fillColor=marker_color,
            fillOpacity=0.7
        ).add_to(marker_cluster)

    # Add legend
    legend_items = []
    for type_name, color in type_colors.items():
        if type_name in valid_df['Customer_Type'].values:
            legend_items.append(f'<div style="display: flex; align-items: center; margin: 2px 0;"><div style="width: 12px; height: 12px; background-color: {color}; border-radius: 50%; margin-right: 8px;"></div><span style="font-size: 12px;">{type_name}</span></div>')
    
    legend_html = f'''
    <div style="position: fixed; 
                bottom: 10px; left: 10px; width: 200px; 
                background-color: white; border: 2px solid grey; z-index: 9999; 
                font-size: 12px; padding: 10px; border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
        <p style="margin: 0 0 8px 0; font-weight: bold;">Project Types</p>
        {''.join(legend_items)}
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    return m

def create_service_distribution(df):
    """Create service distribution pie chart."""
    if df.empty:
        st.warning("⚠️ No service data available for the selected filters.")
        return None
    
    all_services = []
    for services in df['Service_2_list']:
        all_services.extend(services)
    
    if not all_services:
        st.warning("⚠️ No service data available.")
        return None
    
    service_counts = pd.Series(all_services).value_counts()
    
    fig = px.pie(
        values=service_counts.values,
        names=service_counts.index,
        title='Service Distribution',
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(showlegend=True, legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.01))
    
    return fig

def display_project_gallery(df):
    """Display project gallery with Cloudinary images."""
    if df.empty or 'Image' not in df.columns:
        st.warning("⚠️ No project images available for the selected filters.")
        return
    
    projects_with_images = df[df['Image'].notna() & (df['Image'].str.strip() != '')]
    if projects_with_images.empty:
        st.info("ℹ️ No project images available for the current filters.")
        return
    
    st.markdown('<div class="section-header">🖼️ Project Gallery</div>', unsafe_allow_html=True)
    placeholder_image = "https://via.placeholder.com/300x200?text=No+Image"
    
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

    # File path (can be local or will fallback to GitHub)
    csv_file_path = "projectos.csv"

    with st.spinner("🔄 Loading data..."):
        df = load_data_from_csv(csv_file_path)

    if df is None:
        st.error("❌ Failed to load data. Please check the file path or CSV format.")
        st.info("💡 Make sure 'projectos.csv' exists locally or update the GitHub URLs in the code.")
        return
    
    if df.empty:
        st.error("❌ The CSV file is empty or has no valid data.")
        return

    service_options = create_service_mapping(df)

    # Sidebar filters
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
        st.sidebar.info("ℹ️ No service data available")
    
    if st.sidebar.button("🔄 Reset Filters"):
        st.rerun()
    
    st.sidebar.markdown('</div>', unsafe_allow_html=True)

    # Data summary in sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Data Summary")
    st.sidebar.metric("Total Projects", len(df))
    st.sidebar.metric("Project Types", df['Customer_Type'].nunique())
    if service_options:
        st.sidebar.metric("Available Services", len(service_options))

    # Apply filters
    filtered_df = filter_data(df, selected_project_type, selected_service)

    # Show filter information
    if selected_project_type != "All" or selected_service != "All":
        filter_info = []
        if selected_project_type != "All":
            filter_info.append(f"Project Type: **{selected_project_type}**")
        if selected_service != "All":
            filter_info.append(f"Service: **{selected_service}**")
        st.info(f"🔍 Active Filters: {' | '.join(filter_info)} | Showing {len(filtered_df)} of {len(df)} projects")

    if filtered_df.empty:
        st.warning("⚠️ No projects match the current filters. Try adjusting your selection.")
        return

    # KPI Cards
    create_kpi_cards(filtered_df)

    # Map and Service Chart
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown('<div class="section-header">📍 Project Locations</div>', unsafe_allow_html=True)
        map_obj = create_project_map(filtered_df)
        if map_obj:
            st_folium(map_obj, width=None, height=500, use_container_width=True)
            st.info("💡 Click on map markers to see project details, images, and blog links!")
        else:
            st.warning("⚠️ Unable to create map. Check if coordinate data is available.")

    with col2:
        st.markdown('<div class="section-header">📊 Service Distribution</div>', unsafe_allow_html=True)
        service_chart = create_service_distribution(filtered_df)
        if service_chart:
            st.plotly_chart(service_chart, use_container_width=True)

    # Project Gallery
    display_project_gallery(filtered_df)

    # Project Details Table
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

        # Search functionality
        search_term = st.text_input("🔍 Search projects:", placeholder="Enter project name, client, or keyword...")
        if search_term:
            search_cols = [col for col in ['Project Name', 'Client', 'Scope of Work'] if col in table_df.columns]
            if search_cols:
                mask = table_df[search_cols].astype(str).apply(
                    lambda x: x.str.contains(search_term, case=False, na=False)
                ).any(axis=1)
                table_df = table_df[mask]

        # Pagination
        page_size = 10
        total_rows = len(table_df)
        total_pages = max(1, (total_rows - 1) // page_size + 1)
        
        if total_pages > 1:
            page = st.selectbox("📄 Page", range(1, total_pages + 1))
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            display_df = table_df.iloc[start_idx:end_idx]
        else:
            display_df = table_df

        # Column configuration
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
        st.warning("⚠️ No projects match the current filter criteria.")

    # Footer
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
