# Caste & Capital Atlas: Mapping Inequality in Indian Business

This repository hosts an interactive spatial dashboard that maps caste-based inequality and capital accumulation across India using the Sixth Economic Census (EC6).

## 📖 About the Project
While Indian labor and employment have been studied extensively, the ownership of capital and business enterprises remains highly stratified by social group (Caste/Tribe). This project analyzes proprietary enterprise data to highlight where marginalized groups (SC/ST/OBC) are locked into stigmatized or traditional "niches", and where upper-caste capital maintains geographic monopolies.

## 📊 Key Features of the Dashboard
* **Participation Indices (PI):** Measures representation by dividing a group's share of business ownership by their share of the local demographic population. A PI of 1.0 means perfect parity.
* **The Scale Penalty:** Toggle between "All Establishments" and "Directory Establishments (>= 10 workers)" to visualize how marginalized capital vanishes as businesses scale into the formal sector.
* **LISA Spatial Hotspots:** Uses real-time spatial econometrics (Local Moran's I) to map statistically significant contiguous regional monopolies (High-High clusters).
* **Sociological Grouping:** Aggregates 229 specific NIC3 economic activities into 6 broad sociological categories (e.g., *Stigmatized Dalit Niches*, *Modern Knowledge Upper Caste*).

## 🗄️ Data Sources
* **Enterprise Data:** 6th Economic Census of India (EC6) microdata.
* **Demographics:** 2011 Population Census (PCA).
* **Spatial Geometries:** SHRUG PC11 District Shapefiles.
