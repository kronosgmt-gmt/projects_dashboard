import streamlit as st
import pandas as pd
import requests
import io
import folium
from streamlit_folium import st_folium
from urllib.parse import urlparse

# =========================
# PAGE CONFIGURATION
# =========================
st.set_page_config(
    page_title="Kronos GMT Project's Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

CLOUDINARY_CLOUD_NAME = "dmbgxvfo0"

# =========================
# CUSTOM CSS (CORPORATE FUTURISTIC)
# =========================
st.markdown("""
<style>
body, .stApp {
    background: radial-gradient(circle at 20% 30%, #0b0f14 0%, #121b25 100%);
    color: #e0e0e0;
    font-family: 'Segoe UI', sans-serif;
}

.main-header {
    font-size: 2.5rem;
    color: #00eaff;
    text-align: center;
    margin-bottom: 1.5rem;
    text-shadow: 0 0 10px #00eaff;
    letter-spacing: 1px;
}

.section-header {
    font-size: 1.3rem;
    font-weight: 600;
    color: #00eaff;
    margin: 1.5rem 0 0.5rem 0;
    border-bottom: 2px solid rgba(0,234,255,0.3);
    padding-bottom: 0.3rem;
}

.metric-card {
    background: rgba(20, 30, 40, 0.5);
    border: 1px solid rgba(0,234,255,0.2);
    backdrop-filter: blur(8px);
    padding: 1.2rem;
    border-radius: 12px;
    margin-bottom: 1rem;
    text-align: center;
    transition: all 0.3s ease-in-out;
}
.metric-card:hover {
    transform: scale(1.03);
    border-color: #00eaff;
    box-shadow: 0 0 15px rgba(0,234,255,0.3);
}

.stSidebar {
    background: rgba(20, 30, 40, 0.6);
    backdrop-filter: blur(6px);
    border-right: 2px solid rgba(0,234,255,0.2);
}

.stSelectbox > label {
    font-weight: bold;
    color: #00eaff !important;
}

.stButton button {
    background-color: #00eaff;
    color: #0b0f14;
    font-weight: bold;
    border-radius: 6px;
    border: none;
    transition: 0.3s;
}
.stButton button:hover {
    background-color: #009ec2;
    transform: translateY(-2px);
}
</style>
""", unsafe_allow_html=True)

# =========================
# FUNCTIONS
# =========================
def is_valid_cloudinary_url(url, cloud_name=None):
    if not url or pd.isna(url) or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    if cloud_name:
        return (parsed.netloc == "res.cloudinary.com" and url.startswith(f"https://res.cloudinary.com/{cloud_name}/"))
    return parsed.netloc == "res.cloudinary.com"

@st.cache_data(ttl=60)
def load_data():
    url = "https://github.com/kronosgmt-gmt/projects_dashboard/blob/main/proyects.csv"
    try:
        if "github.com" in url:
            url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text), encoding='utf-8')

        df.columns = df.columns.str.strip()
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')

        if 'Customer_Type' not in df.columns:
            df['Customer_Type'] = 'Unknown'

        def clean_services(x):
            if pd.isna(x) or not x:
                return []
            if isinstance(x, str):
                if x.startswith('['):
                    return [s.strip(" '") for s in x.strip("[]").split(',') if s.strip()]
                return [s.strip() for s in x.split(',') if s.strip()]
            return []

        df['Service_2_list'] = df['Service_2'].apply(clean_services) if 'Service_2' in df.columns else [[] for _ in range(len(df))]

        df.dropna(subset=['Longitude', 'Latitude'], inplace=True)
        df = df[(df['Latitude'].between(-90, 90)) & (df['Longitude'].between(-180, 180))]

        if 'Image' in df.columns and CLOUDINARY_CLOUD_NAME:
            df['Image'] = df['Image'].apply(
                lambda x: f"https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/image/upload/{x.strip()}"
                if pd.notna(x) and isinstance(x, str) and x.strip() and not is_valid_cloudinary_url(x, CLOUDINARY_CLOUD_NAME)
                else x
            )

        return df
    except Exception as e:
        st.error(f"⚠️ Error loading data: {e}")
        return pd.DataFrame()

def create_service_mapping(df):
    all_services = set()
    for services in df['Service_2_list']:
        if isinstance(services, list):
            all_services.update(services)
    return sorted([s for s in all_services if s])

def filter_data(df, project_type_filter, service_filter, project_name_filter):
    filtered_df = df.copy()
    if project_type_filter != "All":
        filtered_df = filtered_df[filtered_df['Customer_Type'] == project_type_filter]
    if service_filter != "All":
        filtered_df = filtered_df[filtered_df['Service_2_list'].apply(lambda x: service_filter in x)]
    if project_name_filter != "All":
        filtered_df = filtered_df[filtered_df['Project_Name'] == project_name_filter]
    return filtered_df

def get_project_type_colors(types):
    fixed_colors = {'Commercial': '#00eaff', 'Residential': '#00ffa2', 'Unknown': '#888888'}
    color_map = {}
    extra_colors = ['#ff6f61', '#9b59b6', '#f1c40f']
    for i, t in enumerate(types):
        color_map[t] = fixed_colors.get(t, extra_colors[i % len(extra_colors)])
    return color_map

def create_map(df):
    if df.empty:
        return None
    color_map = get_project_type_colors(df['Customer_Type'].unique())
    m = folium.Map(location=[df['Latitude'].mean(), df['Longitude'].mean()], zoom_start=6, tiles="CartoDB dark_matter")
    for _, row in df.iterrows():
        color = color_map.get(row['Customer_Type'], '#00eaff')
        popup = f"<b>{row['Project_Name']}</b><br>Type: {row['Customer_Type']}"
        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=8,
            popup=popup,
            tooltip=row['Project_Name'],
            color='white',
            fillColor=color,
            fillOpacity=0.9,
            weight=2
        ).add_to(m)
    return m

def display_project_gallery(df):
    st.markdown('<div class="section-header">🖼️ Project Gallery</div>', unsafe_allow_html=True)
    if 'Image' not in df.columns or df['Image'].dropna().empty:
        st.write("No images available.")
        return
    cols = st.columns(4)
    for i, (_, p) in enumerate(df.head(8).iterrows()):
        col = cols[i % 4]
        with col:
            blog_link = p.get('Blog_Link', None)
            if pd.notna(blog_link):
                st.markdown(f"""
                <div style='position:relative; border-radius:10px; overflow:hidden; margin-bottom:10px;'>
                  <a href='{blog_link}' target='_blank'>
                    <img src='{p['Image']}' style='width:100%; border-radius:10px; transition:transform 0.3s ease;'>
                    <div style='position:absolute; bottom:0; width:100%; background:rgba(0,0,0,0.6); 
                                color:white; padding:5px; text-align:center; font-size:0.9rem;'>
                        {p['Project_Name']}<br><span style="color:#00eaff;">📖 Learn More</span>
                    </div>
                  </a>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style='position:relative; border-radius:10px; overflow:hidden; margin-bottom:10px;'>
                  <img src='{p['Image']}' style='width:100%; border-radius:10px; transition:transform 0.3s ease;'>
                  <div style='position:absolute; bottom:0; width:100%; background:rgba(0,0,0,0.6); color:white; padding:5px; text-align:center; font-size:0.9rem;'>
                    {p['Project_Name']}
                  </div>
                </div>
                """, unsafe_allow_html=True)

# =========================
# MAIN APP
# =========================
def main():
    st.markdown('<h1 class="main-header">Kronos GMT – Project Dashboard</h1>', unsafe_allow_html=True)

    df = load_data()
    if df.empty:
        st.stop()

    service_options = create_service_mapping(df)

    with st.sidebar:
        st.markdown("### 🔍 Filters")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

        project_types = ["All"] + sorted(df['Customer_Type'].dropna().unique().tolist())
        selected_type = st.selectbox("🏢 Project Type", project_types, index=0)

        services = ["All"] + service_options if service_options else ["All"]
        selected_service = st.selectbox("🧩 Service", services, index=0)

        # Filter project names dynamically based on previous selections
        temp_filtered = filter_data(df, selected_type, selected_service, "All")
        project_names = ["All"] + sorted(temp_filtered['Project_Name'].dropna().unique().tolist())
        selected_project = st.selectbox("📁 Project Name", project_names, index=0)

    filtered_df = filter_data(df, selected_type, selected_service, selected_project)
    if filtered_df.empty:
        st.warning("No projects match selected filters.")
        st.stop()

    st.markdown(f"📊 **Showing {len(filtered_df)} of {len(df)} total projects**")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown('<div class="section-header">📍 Project Locations</div>', unsafe_allow_html=True)
        map_obj = create_map(filtered_df)
        if map_obj:
            st_folium(map_obj, use_container_width=True, height=500)
        else:
            st.warning("Map could not be generated.")

    with col2:
        st.markdown('<div class="section-header">📊 Project Metrics</div>', unsafe_allow_html=True)
        total_projects = len(filtered_df)
        total_services = sum([len(s) for s in filtered_df['Service_2_list']])
        unique_services = len(set([s for sublist in filtered_df['Service_2_list'] for s in sublist]))

        st.markdown(f"""
        <div class="metric-card"><h3 style="color:#00eaff;">{total_projects}</h3><p>Active Projects</p></div>
        <div class="metric-card"><h3 style="color:#00ffa2;">{unique_services}</h3><p>Unique Services</p></div>
        <div class="metric-card"><h3 style="color:#f1c40f;">{total_services}</h3><p>Total Services Provided</p></div>
        """, unsafe_allow_html=True)

    display_project_gallery(filtered_df)
    st.markdown("---")
    st.caption("© 2025 Kronos GMT | Dashboard by Juan Cano")

if __name__ == "__main__":
    main()
