# Research Notes: Smart Meter Datasets & Information

This document compiles public datasets and detailed information relevant to the themes of GridSight: **Electricity Theft Detection** and **Demand Forecasting**.

## 1. Electricity Theft Detection Datasets

Finding real-world electricity theft datasets is notoriously difficult because power companies are hesitant to release data containing security vulnerabilities or actual criminal activity. However, a few benchmark datasets exist:

### A. The SGCC (State Grid Corporation of China) Dataset
*   **Significance**: This is the most famous and widely cited dataset specifically for electricity theft detection.
*   **Description**: It contains electricity consumption data of 42,372 customers collected over 1,035 days (from Jan 2014 to Oct 2016). It includes a ground truth label for whether a customer is a "normal" user or a "thief" (about 3,615 thieves).
*   **Relevance to GridSight**: This dataset is perfect for training and validating agents like the **CUSUM Agent**, **Peer Agent**, and **Pattern Agent**.
*   **Access**: Available on [Kaggle](https://www.kaggle.com/) (search "SGCC Electricity Theft Dataset") and frequently referenced in IEEE research papers.

### B. Synthetic Theft Injection (The GridSight Approach)
*   Because real theft data is rare and often imbalanced, many researchers (and GridSight) generate normal smart meter profiles and mathematically inject "theft signatures" (e.g., bypassing, flatlining, night-zero).
*   **OpenSynth / LF Energy**: An open-source project that uses deep learning (VAEs) to generate realistic synthetic smart meter load profiles based on real UK data.

---

## 2. Demand/Load Forecasting Datasets

There are excellent, massive open datasets for demand forecasting, primarily from Europe and the UK. These are ideal for training models like **Prophet** and the **Temporal Fusion Transformer (TFT)**.

### A. Low Carbon London (LCL) Dataset
*   **Significance**: The benchmark dataset for household-level load forecasting.
*   **Description**: Half-hourly energy consumption readings from 5,567 London households collected by UK Power Networks between 2011 and 2014. It includes enriched data like weather and Acorn classifications (socio-economic status).
*   **Relevance to GridSight**: Perfect for training the Prophet model to understand household-level seasonality and weather sensitivity.
*   **Access**: Publicly available via the [London Datastore](https://data.london.gov.uk/dataset/smartmeter-energy-use-data-in-london-households) and Kaggle.

### B. CER (Commission for Energy Regulation) Smart Metering Project (Ireland)
*   **Significance**: A comprehensive trial dataset.
*   **Description**: Half-hourly electricity consumption data from over 5,000 residential and SME customers collected during trials between 2009 and 2010.
*   **Access**: Accessed via the Irish Social Science Data Archive (ISSDA) for research purposes.

### C. Smart Energy Research Lab (SERL)
*   **Significance**: A highly detailed modern dataset linking smart meter data with Energy Performance Certificates (EPC) and weather data for thousands of UK households.
*   **Access**: Restricted to accredited researchers via the UK Data Service.

### D. Hugging Face - EDS-Lab/electricity-demand
*   A harmonized compilation of multiple open smart-meter datasets, including weather and metadata, ready to be plugged directly into machine learning pipelines.

---

## 3. Real-World Context: BESCOM

Since GridSight is targeted at **BESCOM** (Bangalore Electricity Supply Company), here is the relevant local context:

*   **Smart Meter Rollout**: BESCOM initiated a massive smart meter rollout in 2025, deploying millions of smart meters across Bangalore.
*   **The Problem**: Historically, India's AT&C (Aggregate Technical & Commercial) losses have averaged 20-25%. A significant portion of this is commercial loss (theft).
*   **Weather Impact**: Bangalore's demand is heavily influenced by summer heatwaves (April/May), driving immense AC load that frequently trips distribution transformers.
*   **Weather Data Integration**: To make forecasting models work in Bangalore, models must integrate local temperature data. The **IMD (India Meteorological Department)** Open Data Portal or the free **Open-Meteo API** are the standard sources for this localized weather injection.

## Conclusion & Next Steps for GridSight

To make GridSight production-ready, the simulated data (`generate_data.py`) can be replaced by taking a benchmark dataset like the **Low Carbon London** dataset, re-scaling the consumption values to match Indian households, aligning the timestamps to the current year, and then injecting the GridSight theft signatures into it. This provides a "real" load profile with known, verifiable anomalies.

### Calibration & Feedback Learning
In production pilots, inspection outcomes can be used to update agent reliability and adaptive thresholds. This keeps the calibrated $P(\text{theft})$ aligned with field reality and reduces false positives without retraining core models.

---

## 4. Open-Source Projects & GitHub References

If you want to review how other developers and researchers have tackled this problem, here are some notable open-source projects on GitHub:

### A. Deep Learning & CNN Approaches
*   **[henryRDlab/ElectricityTheftDetection](https://github.com/henryRDlab/ElectricityTheftDetection)**: A highly starred repository implementing a "Wide and Deep Convolutional Neural Network" (CNN). It is one of the best reference architectures for using the SGCC dataset for theft detection.
*   **[YJJ6342/EnergyData](https://github.com/YJJ6342/EnergyData)**: A comprehensive collection of implementations for energy theft detection using various deep learning techniques, including CNNs, LSTMs, Transformers, and image transformation methods.

### B. Hardware & IoT Implementations
*   **[ask11042004/Iot-power-theft-detector](https://github.com/ask11042004/Iot-power-theft-detector)**: A hardware-focused project. Unlike GridSight's software-only approach, this uses physical Arduino microcontrollers, ZMCT103C current sensors, and ESP8266 Wi-Fi modules to detect unauthorized power usage directly at the wire level and send real-time alerts.

### C. Finding More Resources
*   You can explore the active community tag on GitHub: [**#electricity-theft**](https://github.com/topics/electricity-theft) which aggregates ongoing research and student projects globally.
