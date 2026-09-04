import streamlit as st
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import os
import io
import numpy as np

try:
    from esda.moran import Moran_Local
    from libpysal.weights import Queen
    import matplotlib.colors as colors
    HAS_ESDA = True
except ImportError:
    HAS_ESDA = False

st.set_page_config(layout="wide", page_title="India EC6 Caste Atlas - Ultimate")

def classify_sociological(nic3):
    dalit = ['151', '152', '101', '381', '382', '370', '812', '960']
    tribal = ['021', '022', '023', '024', '051', '052', '061', '062', '071', '072', '081', '089', '091', '099']
    obc_artisan = ['131', '139', '161', '162', '110', '120', '239', '310', '321', '103', '104']
    upper_caste = ['620', '641', '642', '643', '649', '651', '652', '653', '661', '662', '663', '691', '692', '701', '702', '711', '712', '721', '722', '731', '732', '741', '742', '749', '853', '210', '291']
    trade_vaishya = ['461', '462', '463', '464', '465', '466', '469']
    
    if str(nic3) in dalit: return "Stigmatized / Polluting (Dalit Niche)"
    if str(nic3) in tribal: return "Forestry & Extractive (Tribal Niche)"
    if str(nic3) in obc_artisan: return "Traditional Artisan / Craft (OBC Niche)"
    if str(nic3) in upper_caste: return "Modern Knowledge & Capital (Upper Caste)"
    if str(nic3) in trade_vaishya: return "Traditional Mercantile (Vaishya Niche)"
    return "Petty / General Economy"

@st.cache_data
def load_base_data():
    base = os.path.dirname(__file__)
    granular_path = os.path.join(base, 'data', 'india_ec6_district_nic3_expanded_granular.csv.gz')
    df = pd.read_csv(granular_path, dtype={'pc11_state_id': 'category', 'pc11_district_id': 'category', 'NIC3': 'category', 'SG': 'category', 'SECTOR': 'category'})
    df['count'] = pd.to_numeric(df['count'], downcast='integer')
    df['pc11_district_id'] = df['pc11_district_id'].astype(str).str.zfill(3).astype('category')
    df['NIC3'] = df['NIC3'].astype(str).str.zfill(3).astype('category')
    
    cw_path = os.path.join(base, 'data', 'india_ec6_nic3_typology_crosswalk.csv')
    cw = pd.read_csv(cw_path, dtype=str)
    cw['nic3'] = cw['nic3'].str.zfill(3)
    
    # Pre-merge names
    df = df.merge(cw[['nic3', 'nic3_label', 'broad_sector_label']], left_on='NIC3', right_on='nic3', how='left')
    df['nic3_label'] = df['nic3_label'].fillna("Unknown Sector")
    df['sociological_category'] = df['NIC3'].apply(classify_sociological)
    df['formatted_name'] = df['NIC3'] + " - " + df['nic3_label']
    
    # Load Census for demographics and denominators
    census_path = os.path.join(base, 'data', 'india_census2011_sc_st_population_pc11_district.csv')
    census = pd.read_csv(census_path, dtype=str)
    census['pc11_district_id'] = census['pc11_district_id'].str.zfill(3)
    census['sc_pop_share_dist'] = pd.to_numeric(census['sc_population_share_pct'], errors='coerce')
    census['st_pop_share_dist'] = pd.to_numeric(census['st_population_share_pct'], errors='coerce')
    
    # Load Shapefile and heavily optimize memory
    shp_path = os.path.join(base, 'data', 'shrug-pc11dist-poly-shp.zip')
    gdf = gpd.read_file(f'zip://{shp_path}')
    # CRITICAL OOM FIX: Simplify geometry before caching it in RAM
    gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.01, preserve_topology=True)
    gdf = gdf[['pc11_d_id', 'geometry']] # Drop unneeded heavy columns
    dist_col = 'pc11_d_id'
    gdf[dist_col] = gdf[dist_col].astype(str).str.zfill(3)
    
    # For state dropdowns
    state_cw = pd.read_csv(os.path.join(base, 'data', 'india_ec6_district_to_pc11_crosswalk.csv'), dtype=str)
    
    return df, gdf, dist_col, census, cw, state_cw

st.title("EC6 Caste & Capital Atlas: Ultimate Analytics")

with st.expander("📖 **About this Atlas (Click to read)**", expanded=False):
    st.markdown("""
    **Welcome to the Caste & Capital Atlas.** This interactive dashboard maps the deeply stratified landscape of business ownership across India using the Sixth Economic Census (EC6).
    
    **How to read the data:**
    * **Participation Index (PI):** We measure representation using a Participation Index *(Ownership Share ÷ Demographic Population Share)*. A PI of `1.0` means exact parity. A PI of `2.0` means a group owns twice as many businesses as their population share would predict.
    * **The Scale Penalty:** By default, the map shows *all* businesses (including tiny street vendors and single-person stalls). Toggle the **Scale Penalty** to *"Directory Only (>= 10 Workers)"* to see who actually controls larger, formal capital.
    * **LISA Spatial Hotspots:** Check the LISA box to run real-time spatial econometrics. It highlights **Red clusters** where high-ownership districts are surrounded by other high-ownership districts (continuous regional monopolies).
    """)

try:
    df, gdf, dist_col, census, cw, state_cw = load_base_data()
    
    tab1, tab2, tab3 = st.tabs(["🗺️ Advanced Map Explorer", "🏆 Rankings", "📍 District Dominance"])
    
    # ---------------------------------------------------------
    # TAB 1: ADVANCED MAP EXPLORER
    # ---------------------------------------------------------
    with tab1:
        c1, c2 = st.columns([1, 3])
        with c1:
            st.markdown("### 1. Sector Selection")
            soc_cats = ["All"] + list(df['sociological_category'].unique())
            sel_soc = st.selectbox("Sociological Category", soc_cats, help="Filter the options below by a broad sociological bucket.")
            
            map_level = st.radio("Map Level", ["Specific NIC3 Sector", "Entire Sociological Category (Aggregate)"], help="Choose whether to map a single specific industry, or an entire broad category combined.")
            
            if map_level == "Specific NIC3 Sector":
                filtered_df = df.copy()
                if sel_soc != "All": filtered_df = filtered_df[filtered_df['sociological_category'] == sel_soc]
                nic_options = sorted(filtered_df['formatted_name'].unique()) if not filtered_df.empty else []
                selected_entity = st.selectbox("NIC3 Sector", nic_options, help="Select the exact NIC 3-digit economic activity.")
            else:
                cat_options = [c for c in soc_cats if c != "All"]
                default_idx = cat_options.index(sel_soc) if sel_soc in cat_options else 0
                selected_entity = st.selectbox("Select Sociological Category to Aggregate", cat_options, index=default_idx, help="This will combine all NIC3 sectors within this bucket and map their total capital footprint.")
            
            group = st.selectbox("Social Group", ["SC", "ST", "OBC", "Others"], help="Select which social group's Participation Index to map.")
            pi_col_map = {"SC": "SCPI", "ST": "STPI", "OBC": "OBCPI", "Others": "OtherPI"}
            pi_col = pi_col_map[group]
            
            st.markdown("### 2. Market Filters")
            sel_sector = st.radio("Rural / Urban", ["Both", "Rural Only", "Urban Only"], help="Isolate the map to only show businesses located in rural villages or urban cities.")
            sel_scale = st.radio("Scale Penalty", ["All Establishments", "Directory Only (>= 10 Workers)"], help="Filter out micro-enterprises. 'Directory Only' forces the map to only calculate ownership for businesses with 10 or more workers.")
            
            st.markdown("### 3. Spatial Analytics")
            use_lisa = st.checkbox("Highlight LISA Hotspots", help="Runs a Local Moran's I spatial regression. Colors only districts that form a statistically significant cluster of continuous monopolies (High-High).")
            overlay_var = st.selectbox("Demographic Overlay", ["None", "Urbanization Rate (%)", "Literacy Rate (%)"], help="Plot a demographic variable side-by-side to visually compare spatial correlations.")
            
            st.markdown("---")
            generate_btn = st.button("🚀 Generate Map", type="primary", use_container_width=True)
            
        with c2:
            if not generate_btn:
                st.info("👈 Please select your desired filters on the left and click **'Generate Map'** to run the spatial analytics.")
            elif selected_entity:
                with st.spinner("Crunching data and rendering high-resolution maps... This may take a few seconds."):
                    # Apply Filters
                if map_level == "Specific NIC3 Sector":
                    nic_code = selected_entity.split(" - ")[0]
                    sub = df[df['NIC3'] == nic_code].copy()
                else:
                    sub = df[df['sociological_category'] == selected_entity].copy()
                    
                if sel_sector == "Rural Only": sub = sub[sub['SECTOR'] == '1']
                if sel_sector == "Urban Only": sub = sub[sub['SECTOR'] == '2']
                if sel_scale == "Directory Only (>= 10 Workers)": sub = sub[sub['is_directory'] == 1]
                
                # Pivot by District
                pivoted = sub.pivot_table(index='pc11_district_id', columns='SG', values='count', aggfunc='sum', fill_value=0).reset_index()
                pivoted = pivoted.rename(columns={'1': 'sc_count', '2': 'st_count', '3': 'obc_count', '9': 'others_count'})
                for col in ['sc_count', 'st_count', 'obc_count', 'others_count']:
                    if col not in pivoted.columns: pivoted[col] = 0
                
                pivoted['total_coded'] = pivoted['sc_count'] + pivoted['st_count'] + pivoted['obc_count'] + pivoted['others_count']
                pivoted = pivoted[pivoted['total_coded'] > 0]
                
                pivoted['sc_own_share'] = (pivoted['sc_count'] / pivoted['total_coded']) * 100
                pivoted['st_own_share'] = (pivoted['st_count'] / pivoted['total_coded']) * 100
                pivoted['obc_own_share'] = (pivoted['obc_count'] / pivoted['total_coded']) * 100
                pivoted['others_own_share'] = (pivoted['others_count'] / pivoted['total_coded']) * 100
                
                # Merge Demographics
                merged = pivoted.merge(census, on='pc11_district_id', how='left')
                merged['SCPI'] = np.where(merged['sc_pop_share_dist'] > 0, merged['sc_own_share'] / merged['sc_pop_share_dist'], 0)
                merged['STPI'] = np.where(merged['st_pop_share_dist'] > 0, merged['st_own_share'] / merged['st_pop_share_dist'], 0)
                
                # Approximations for OBC/Others since we don't have district level
                merged['OBCPI'] = merged['obc_own_share'] / 45.0
                merged['OtherPI'] = merged['others_own_share'] / 30.0
                
                st.write(f"### {group} Representation: {selected_entity}")
                st.write(f"Total Establishments matching criteria: **{pivoted['total_coded'].sum():,}**")
                
                map_df = gdf.merge(merged, left_on=dist_col, right_on='pc11_district_id', how='left')
                map_df[pi_col] = map_df[pi_col].fillna(0)
                
                # Merge Demographic Overlay
                if overlay_var != "None":
                    dem_path = os.path.join(os.path.dirname(__file__), 'data', 'india_census2011_demographics_pc11_district.csv')
                    dem_df = pd.read_csv(dem_path, dtype=str)
                    dem_df['pc11_district_id'] = dem_df['pc11_district_id'].str.zfill(3)
                    dem_df['urbanization_rate'] = pd.to_numeric(dem_df['urbanization_rate'], errors='coerce')
                    dem_df['literacy_rate'] = pd.to_numeric(dem_df['literacy_rate'], errors='coerce')
                    map_df = map_df.merge(dem_df, left_on=dist_col, right_on='pc11_district_id', how='left')
                
                use_interactive = st.checkbox("Enable Interactive Hover Map (Slightly slower to load)", value=False)
                
                export_name = selected_entity.split(" - ")[0].replace("/", "_").replace(" ", "_").lower()
                
                if use_interactive:
                    import plotly.express as px
                    st.write("*Interactive Mode Enabled. Hover over districts to see data.*")
                    
                    # Convert to geographic coordinate system for Plotly Mapbox
                    try:
                        map_df_wgs = map_df.to_crs(epsg=4326)
                        
                        fig_inter = px.choropleth_map(map_df_wgs, geojson=map_df_wgs.geometry, locations=map_df_wgs.index, 
                                                         color=pi_col,
                                                         hover_name="pc11_district_name",
                                                         hover_data={"map_state_name": True, pi_col: True},
                                                         color_continuous_scale="Blues",
                                                         range_color=[0, 3.0],
                                                         map_style="carto-positron",
                                                         zoom=3.5, center = {"lat": 22.0, "lon": 78.0},
                                                         opacity=0.7,
                                                         title=f"{group} Representation: {selected_entity}")
                        fig_inter.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
                        st.plotly_chart(fig_inter, width="stretch")
                    except Exception as e:
                        st.error(f"Could not render interactive map: {e}")
                
                # Always generate static map for downloading and LISA
                num_plots = 2 if overlay_var != "None" else 1
                fig, axes = plt.subplots(1, num_plots, figsize=(12 * num_plots, 10))
                ax1 = axes[0] if num_plots > 1 else axes
                
                if use_lisa and HAS_ESDA:
                    # LISA Logic
                    map_df['lisa_val'] = map_df[pi_col].fillna(0)
                    clean_map = map_df[~map_df.geometry.is_empty & map_df.geometry.notna()].copy()
                    clean_map = clean_map.reset_index(drop=True)
                    
                    if len(clean_map) > 0:
                        w = Queen.from_dataframe(clean_map)
                        w.transform = 'r'
                        lisa = Moran_Local(clean_map['lisa_val'].values, w)
                        
                        spots = ['None', 'High-High (Cluster)', 'Low-High (Outlier)', 'Low-Low (Cluster)', 'High-Low (Outlier)']
                        colors_list = ['lightgrey', 'red', 'lightblue', 'blue', 'pink']
                        cmap_lisa = colors.ListedColormap(colors_list)
                        
                        sig = 1 * (lisa.p_sim < 0.05)
                        hotspots = sig * lisa.q
                        clean_map['spot'] = hotspots
                        
                        clean_map.plot(column='spot', cmap=cmap_lisa, categorical=True, ax=ax1, edgecolor='black', linewidth=0.1)
                        import textwrap
                        wrapped_title = "\n".join(textwrap.wrap(f"LISA Spatial Clusters: {group} in {selected_entity}", width=50))
                        ax1.set_title(f"{wrapped_title}\n({sel_scale} | {sel_sector})", fontsize=14)
                        st.write("*Note: Red shows High-High clusters (Statistically significant continuous regional monopolies).*")
                else:
                    cmap_map = {"SC": "Reds", "ST": "Oranges", "OBC": "Greens", "Others": "Blues"}
                    map_df.plot(column=pi_col, ax=ax1, cmap=cmap_map[group], legend=True,
                                legend_kwds={'label': f'{group} Participation Index (PI)', 'shrink': 0.6},
                                vmax=3.0, edgecolor='black', linewidth=0.1)
                    
                    import textwrap
                    wrapped_title = "\n".join(textwrap.wrap(f"{group} Ownership: {selected_entity}", width=50))
                    ax1.set_title(f"{wrapped_title}\n({sel_scale} | {sel_sector})", fontsize=14)
                
                ax1.axis('off')
                
                # Plot Demographic Overlay if selected
                if overlay_var != "None":
                    ax2 = axes[1]
                    dem_col = 'urbanization_rate' if overlay_var == "Urbanization Rate (%)" else 'literacy_rate'
                    map_df.plot(column=dem_col, ax=ax2, cmap="Purples", legend=True,
                                legend_kwds={'label': overlay_var, 'shrink': 0.6},
                                edgecolor='black', linewidth=0.1)
                    ax2.set_title(f"Overlay: {overlay_var}", fontsize=14)
                    ax2.axis('off')
                
                st.pyplot(fig)
                
                # Download Button
                buf = io.BytesIO()
                fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
                st.download_button(
                    label="Download High-Res Map",
                    data=buf.getvalue(),
                    file_name=f"map_{group}_{export_name}.png",
                    mime="image/png"
                )
    
    # ---------------------------------------------------------
    # TAB 2: RANKINGS
    # ---------------------------------------------------------
    with tab2:
        st.markdown("### Top/Bottom Sector Rankings")
        
        all_states = sorted(state_cw['map_state_name'].dropna().unique())
        sel_state = st.selectbox("Select Region for Rankings", ["All India (National)"] + list(all_states))
        
        rank_df = df.copy()
        if sel_state != "All India (National)":
            state_id = state_cw[state_cw['map_state_name'] == sel_state]['pc11_state_id'].iloc[0].zfill(2)
            rank_df = rank_df[rank_df['pc11_state_id'] == state_id]
        
        agg_df = rank_df.groupby(['NIC3', 'nic3_label', 'sociological_category']).agg({'count': 'sum'}).reset_index()
        # To get the PI we need to pivot by SG first
        piv = rank_df.pivot_table(index=['NIC3', 'nic3_label', 'sociological_category'], columns='SG', values='count', aggfunc='sum', fill_value=0).reset_index()
        piv = piv.rename(columns={'1': 'sc_count', '2': 'st_count', '3': 'obc_count', '9': 'others_count'})
        for c in ['sc_count', 'st_count', 'obc_count', 'others_count']:
            if c not in piv.columns: piv[c] = 0
            
        piv['total_coded'] = piv['sc_count'] + piv['st_count'] + piv['obc_count'] + piv['others_count']
        
        NAT_SC, NAT_ST, NAT_OBC, NAT_OTH = 16.6, 8.6, 45.0, 29.8
        piv['SCPI'] = ((piv['sc_count'] / piv['total_coded']) * 100) / NAT_SC
        piv['STPI'] = ((piv['st_count'] / piv['total_coded']) * 100) / NAT_ST
        piv['OBCPI'] = ((piv['obc_count'] / piv['total_coded']) * 100) / NAT_OBC
        piv['OtherPI'] = ((piv['others_count'] / piv['total_coded']) * 100) / NAT_OTH
        
        min_est = st.slider("Minimum Establishments (to filter out noise)", 0, 50000, 5000)
        large_agg = piv[piv['total_coded'] >= min_est]
        
        rank_group = st.selectbox("Rank for Social Group", ["SC", "ST", "OBC", "Others"], key="rank_group")
        pi_col_map = {"SC": "SCPI", "ST": "STPI", "OBC": "OBCPI", "Others": "OtherPI"}
        r_col = pi_col_map[rank_group]
        
        r_col1, r_col2 = st.columns(2)
        with r_col1:
            st.markdown(f"**Top 15 {rank_group} Niches in {sel_state}**")
            st.dataframe(large_agg.sort_values(r_col, ascending=False).head(15)[['NIC3', 'nic3_label', r_col, 'sociological_category', 'total_coded']])
        with r_col2:
            st.markdown(f"**Bottom 15 {rank_group} Locked-Out in {sel_state}**")
            st.dataframe(large_agg.sort_values(r_col, ascending=True).head(15)[['NIC3', 'nic3_label', r_col, 'sociological_category', 'total_coded']])

    # ---------------------------------------------------------
    # TAB 3: DISTRICT DOMINANCE
    # ---------------------------------------------------------
    with tab3:
        st.markdown("### Most Exclusive Sector per District")
        
        c1, c2 = st.columns(2)
        with c1:
            state_opts = sorted(state_cw['map_state_name'].dropna().unique())
            dom_state = st.selectbox("1. Select State", state_opts)
        
        with c2:
            state_id_dom = state_cw[state_cw['map_state_name'] == dom_state]['pc11_state_id'].iloc[0].zfill(2)
            state_districts = state_cw[state_cw['pc11_state_id'].str.zfill(2) == state_id_dom]
            cw_dict = dict(zip(state_districts['pc11_district_id'].str.zfill(3), state_districts['pc11_district_name']))
            dist_options = [f"{d} - {cw_dict.get(d, 'Unknown')}" for d in sorted(cw_dict.keys())]
            
            sel_dist_str = st.selectbox("2. Select District", dist_options)
        
        if sel_dist_str:
            sel_dist = sel_dist_str.split(" - ")[0]
            dist_data = df[df['pc11_district_id'] == sel_dist].copy()
            
            piv_dist = dist_data.pivot_table(index=['NIC3', 'nic3_label'], columns='SG', values='count', aggfunc='sum', fill_value=0).reset_index()
            piv_dist = piv_dist.rename(columns={'1': 'sc', '2': 'st', '3': 'obc', '9': 'oth'})
            for c in ['sc', 'st', 'obc', 'oth']:
                if c not in piv_dist.columns: piv_dist[c] = 0
                
            piv_dist['tot'] = piv_dist['sc'] + piv_dist['st'] + piv_dist['obc'] + piv_dist['oth']
            piv_dist = piv_dist[piv_dist['tot'] > 50]
            
            if not piv_dist.empty:
                # get dist demog
                d_cen = census[census['pc11_district_id'] == sel_dist]
                sc_p = d_cen['sc_pop_share_dist'].iloc[0] if not d_cen.empty else 16.6
                st_p = d_cen['st_pop_share_dist'].iloc[0] if not d_cen.empty else 8.6
                
                piv_dist['SCPI'] = ((piv_dist['sc']/piv_dist['tot'])*100) / (sc_p if sc_p>0 else 16.6)
                piv_dist['STPI'] = ((piv_dist['st']/piv_dist['tot'])*100) / (st_p if st_p>0 else 8.6)
                piv_dist['OBCPI'] = ((piv_dist['obc']/piv_dist['tot'])*100) / 45.0
                piv_dist['OtherPI'] = ((piv_dist['oth']/piv_dist['tot'])*100) / 30.0
                
                st.write(f"Showing sectors with >50 establishments in **{sel_dist_str} ({dom_state})**")
                
                d1, d2 = st.columns(2)
                with d1:
                    st.write("##### Highest SC Concentration (SCPI)")
                    st.dataframe(piv_dist.sort_values('SCPI', ascending=False).head(5)[['nic3_label', 'SCPI', 'tot']])
                    st.write("##### Highest OBC Concentration (OBCPI)")
                    st.dataframe(piv_dist.sort_values('OBCPI', ascending=False).head(5)[['nic3_label', 'OBCPI', 'tot']])
                with d2:
                    st.write("##### Highest ST Concentration (STPI)")
                    st.dataframe(piv_dist.sort_values('STPI', ascending=False).head(5)[['nic3_label', 'STPI', 'tot']])
                    st.write("##### Highest Upper Caste Concentration (OtherPI)")
                    st.dataframe(piv_dist.sort_values('OtherPI', ascending=False).head(5)[['nic3_label', 'OtherPI', 'tot']])
            else:
                st.warning("Not enough data in this district.")

except Exception as e:
    st.error(f"Error loading data: {e}")
