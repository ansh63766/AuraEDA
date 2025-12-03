import pandas as pd
import numpy as np

def generate_titanic():
    np.random.seed(42)
    n = 500
    passenger_id = np.arange(1, n + 1)
    pclass = np.random.choice([1, 2, 3], size=n, p=[0.24, 0.21, 0.55])
    sex = np.random.choice(["male", "female"], size=n, p=[0.60, 0.40])
    
    # Calculate age, depend on pclass
    age = np.random.normal(loc=30 - 2 * pclass, scale=12, size=n)
    age = np.clip(age, 1, 80)
    age[np.random.rand(n) < 0.15] = np.nan # 15% nulls
    
    # Fare depends on pclass
    base_fare = {1: 85.0, 2: 25.0, 3: 13.0}
    fare = np.array([base_fare[pc] + np.random.exponential(scale=base_fare[pc]*0.5) for pc in pclass])
    
    embarked = np.random.choice(["S", "C", "Q"], size=n, p=[0.72, 0.18, 0.10])
    
    # Survival probability depends on sex, pclass, and age
    surv_prob = 0.5 + 0.3 * (sex == "female") - 0.15 * (pclass == 3) - 0.05 * (np.nan_to_num(age) > 50)
    surv_prob = np.clip(surv_prob, 0.05, 0.95)
    survived = (np.random.rand(n) < surv_prob).astype(int)
    
    df = pd.DataFrame({
        "PassengerId": passenger_id,
        "Survived": survived,
        "Pclass": pclass,
        "Sex": sex,
        "Age": age,
        "Fare": np.round(fare, 2),
        "Embarked": embarked,
        "SurvivalLeak": survived # perfect predictor check
    })
    return df

def generate_iris():
    np.random.seed(42)
    n = 150
    species = np.random.choice(["setosa", "versicolor", "virginica"], size=n)
    
    sepal_len = []
    sepal_wid = []
    petal_len = []
    petal_wid = []
    
    specs = {
        "setosa": (5.0, 3.4, 1.4, 0.2),
        "versicolor": (5.9, 2.7, 4.2, 1.3),
        "virginica": (6.5, 2.9, 5.5, 2.0)
    }
    
    for sp in species:
        m = specs[sp]
        sepal_len.append(np.random.normal(m[0], 0.35))
        sepal_wid.append(np.random.normal(m[1], 0.3))
        petal_len.append(np.random.normal(m[2], 0.4))
        petal_wid.append(np.random.normal(m[3], 0.2))
        
    df = pd.DataFrame({
        "sepal_length": np.round(sepal_len, 1),
        "sepal_width": np.round(sepal_wid, 1),
        "petal_length": np.round(petal_len, 1),
        "petal_width": np.round(petal_wid, 1),
        "species": species
    })
    return df

def generate_world_pop():
    np.random.seed(42)
    n = 200
    countries = ["China", "India", "USA", "Indonesia", "Pakistan", "Brazil", "Nigeria", "Bangladesh", "Russia", "Mexico"]
    df_list = []
    for c in countries:
        base_pop = np.random.randint(100, 1000) * 1000000
        growth_rate = np.random.uniform(0.005, 0.025)
        years = np.arange(2010, 2026)
        pop = [int(base_pop * ((1 + growth_rate) ** (yr - 2010))) for yr in years]
        df_list.append(pd.DataFrame({
            "Country": [c] * len(years),
            "Year": years,
            "Population": pop,
            "GrowthRate": [growth_rate] * len(years)
        }))
    return pd.concat(df_list, ignore_index=True)

def generate_text_reviews():
    np.random.seed(42)
    n = 300
    categories = ["Electronics", "Books", "Clothing", "Home", "Beauty"]
    cat = np.random.choice(categories, size=n)
    rating = np.random.choice([1, 2, 3, 4, 5], size=n, p=[0.05, 0.08, 0.12, 0.35, 0.40])
    
    adjectives_good = ["excellent", "superb", "highly recommended", "awesome", "perfect", "fantastic", "amazing"]
    adjectives_bad = ["poor", "disappointing", "awful", "waste of money", "broken", "terrible", "bad quality"]
    nouns = ["product", "item", "purchase", "delivery", "packaging", "service", "experience"]
    
    reviews = []
    for r in rating:
        adj = np.random.choice(adjectives_good if r >= 4 else adjectives_bad)
        noun = np.random.choice(nouns)
        reviews.append(f"This was an {adj} {noun}. Will buy again!")
        
    df = pd.DataFrame({
        "ReviewID": np.arange(1000, 1000 + n),
        "Category": cat,
        "Rating": rating,
        "ReviewText": reviews
    })
    return df

def generate_climate():
    np.random.seed(42)
    n = 480 # 40 years of monthly data
    dates = pd.date_range(start="1985-01-01", periods=n, freq="M")
    temp_trend = np.linspace(-0.2, 1.2, n)
    seasonal = np.sin(2 * np.pi * dates.month / 12.0) * 8.0
    noise = np.random.normal(0, 0.5, size=n)
    temp = 14.0 + temp_trend + seasonal + noise
    co2 = 345.0 + np.linspace(0, 75, n) + np.random.normal(0, 0.2, size=n)
    
    df = pd.DataFrame({
        "Date": dates.strftime("%Y-%m-%d"),
        "GlobalTempAnomaly": np.round(temp_trend + noise, 3),
        "AverageTemperature": np.round(temp, 2),
        "CO2_PPM": np.round(co2, 1)
    })
    return df

def generate_california_housing():
    np.random.seed(42)
    n = 400
    latitude = np.random.uniform(32.5, 42.0, size=n)
    longitude = np.random.uniform(-124.3, -114.3, size=n)
    house_age = np.random.randint(1, 52, size=n)
    median_income = np.random.normal(3.8, 1.5, size=n)
    median_income = np.clip(median_income, 0.5, 15.0)
    
    # price depends on income, age, coordinates (coasts are expensive)
    coast_dist = np.abs(longitude - (-122.0)) + np.abs(latitude - 37.0) # proximity to bay area
    price = 100000 * median_income + 1500 * house_age - 20000 * coast_dist + np.random.normal(50000, 20000, size=n)
    price = np.clip(price, 15000, 500001)
    
    df = pd.DataFrame({
        "HouseAge": house_age.astype(float),
        "MedianIncome": np.round(median_income, 4),
        "Latitude": np.round(latitude, 4),
        "Longitude": np.round(longitude, 4),
        "MedianHouseValue": np.round(price, 2)
    })
    return df

def generate_customer_churn():
    np.random.seed(42)
    n = 500
    gender = np.random.choice(["Male", "Female"], size=n)
    tenure = np.random.randint(1, 73, size=n)
    contract = np.random.choice(["Month-to-month", "One year", "Two year"], size=n, p=[0.55, 0.23, 0.22])
    monthly_charges = np.random.normal(65, 30, size=n)
    monthly_charges = np.clip(monthly_charges, 18, 118)
    
    # Churn depends on contract and tenure
    churn_prob = 0.4 - 0.005 * tenure - 0.2 * (contract != "Month-to-month")
    churn_prob = np.clip(churn_prob, 0.02, 0.90)
    churn = (np.random.rand(n) < churn_prob).astype(int)
    
    df = pd.DataFrame({
        "CustomerID": [f"CUST_{i:04d}" for i in range(1, n + 1)],
        "Gender": gender,
        "Tenure": tenure,
        "Contract": contract,
        "MonthlyCharges": np.round(monthly_charges, 2),
        "Churn": churn
    })
    return df

def generate_penguins():
    np.random.seed(42)
    n = 344
    species = np.random.choice(["Adelie", "Chinstrap", "Gentoo"], size=n, p=[0.44, 0.20, 0.36])
    island = np.random.choice(["Torgersen", "Biscoe", "Dream"], size=n)
    
    bill_len = []
    bill_dep = []
    flip_len = []
    body_mass = []
    sex = np.random.choice(["MALE", "FEMALE"], size=n)
    
    specs = {
        "Adelie": (38.8, 18.3, 190.0, 3700.0),
        "Chinstrap": (48.8, 18.4, 195.0, 3730.0),
        "Gentoo": (47.5, 15.0, 217.0, 5080.0)
    }
    
    for i in range(n):
        m = specs[species[i]]
        offset = 1.2 if sex[i] == "MALE" else -1.2
        bill_len.append(np.random.normal(m[0] + offset*0.5, 1.5))
        bill_dep.append(np.random.normal(m[1] + offset*0.2, 0.8))
        flip_len.append(np.random.normal(m[2] + offset*2.0, 5.0))
        body_mass.append(np.random.normal(m[3] + offset*200.0, 300.0))
        
    df = pd.DataFrame({
        "species": species,
        "island": island,
        "bill_length_mm": np.round(bill_len, 1),
        "bill_depth_mm": np.round(bill_dep, 1),
        "flipper_length_mm": np.round(flip_len, 1),
        "body_mass_g": np.round(body_mass, 1),
        "sex": sex
    })
    # Add minor null values to bill and sex
    df.loc[df.sample(frac=0.03).index, "bill_length_mm"] = np.nan
    df.loc[df.sample(frac=0.04).index, "sex"] = np.nan
    return df

def generate_diamonds():
    np.random.seed(42)
    n = 450
    carat = np.random.exponential(scale=0.7, size=n) + 0.2
    carat = np.clip(carat, 0.2, 3.5)
    cut = np.random.choice(["Ideal", "Premium", "Very Good", "Good", "Fair"], size=n, p=[0.40, 0.26, 0.22, 0.09, 0.03])
    color = np.random.choice(["D", "E", "F", "G", "H", "I", "J"], size=n)
    
    # price depends strongly on carat, and cut
    cut_factor = {"Ideal": 1.1, "Premium": 1.05, "Very Good": 1.0, "Good": 0.9, "Fair": 0.8}
    price = [int(3500 * (carat[i] ** 1.3) * cut_factor[cut[i]] + np.random.normal(200, 100)) for i in range(n)]
    price = [max(326, p) for p in price]
    
    df = pd.DataFrame({
        "Carat": np.round(carat, 2),
        "Cut": cut,
        "Color": color,
        "Price": price
    })
    return df

def generate_air_quality():
    np.random.seed(42)
    n = 350
    pm25 = np.random.exponential(scale=25, size=n) + 5.0
    no2 = np.random.normal(15, 8, size=n)
    no2 = np.clip(no2, 1.0, 60.0)
    ozone = np.random.normal(35, 15, size=n)
    ozone = np.clip(ozone, 5.0, 100.0)
    
    aqi = pm25 * 1.2 + no2 * 0.4 + ozone * 0.3 + np.random.normal(5, 2, size=n)
    aqi_class = []
    for val in aqi:
        if val <= 50: aqi_class.append("Good")
        elif val <= 100: aqi_class.append("Moderate")
        elif val <= 150: aqi_class.append("Unhealthy for Sensitive")
        else: aqi_class.append("Unhealthy")
        
    df = pd.DataFrame({
        "PM2_5": np.round(pm25, 2),
        "NO2": np.round(no2, 2),
        "Ozone": np.round(ozone, 2),
        "AQI_Score": np.round(aqi, 1),
        "AQI_Class": aqi_class
    })
    return df

def generate_weather():
    np.random.seed(42)
    n = 365
    date = pd.date_range(start="2025-01-01", periods=n, freq="D")
    temp = 12.0 + 10.0 * np.sin(2 * np.pi * date.dayofyear / 365.0) + np.random.normal(0, 3, size=n)
    humidity = np.random.uniform(30, 95, size=n)
    wind_speed = np.random.exponential(scale=8, size=n) + 2.0
    
    # Rain depends on humidity
    rain_prob = (humidity - 20) / 100.0
    rain_prob = np.clip(rain_prob, 0.05, 0.95)
    rain = (np.random.rand(n) < rain_prob).astype(int)
    
    df = pd.DataFrame({
        "Date": date.strftime("%Y-%m-%d"),
        "Temperature": np.round(temp, 1),
        "Humidity": np.round(humidity, 1),
        "WindSpeed": np.round(wind_speed, 1),
        "Rain": rain
    })
    return df

def generate_retail_sales():
    np.random.seed(42)
    n = 500
    transaction_id = [f"TXN_{i:06d}" for i in range(1, n + 1)]
    category = np.random.choice(["Electronics", "Clothing", "Groceries", "Home Decor", "Stationery"], size=n)
    quantity = np.random.choice([1, 2, 3, 4, 5], size=n, p=[0.40, 0.30, 0.15, 0.10, 0.05])
    
    base_price = {"Electronics": 250.0, "Clothing": 45.0, "Groceries": 8.0, "Home Decor": 65.0, "Stationery": 12.0}
    unit_price = [base_price[cat] + np.random.uniform(-base_price[cat]*0.1, base_price[cat]*0.2) for cat in category]
    revenue = [q * p for q, p in zip(quantity, unit_price)]
    
    df = pd.DataFrame({
        "TransactionID": transaction_id,
        "Category": category,
        "Quantity": quantity,
        "UnitPrice": np.round(unit_price, 2),
        "TotalRevenue": np.round(revenue, 2)
    })
    return df

def get_sample_dataset(name: str):
    name_lower = name.lower()
    if "titanic" in name_lower:
        return generate_titanic()
    elif "iris" in name_lower:
        return generate_iris()
    elif "world" in name_lower or "pop" in name_lower:
        return generate_world_pop()
    elif "text" in name_lower or "review" in name_lower:
        return generate_text_reviews()
    elif "climate" in name_lower:
        return generate_climate()
    elif "california" in name_lower or "house" in name_lower:
        return generate_california_housing()
    elif "churn" in name_lower:
        return generate_customer_churn()
    elif "penguin" in name_lower:
        return generate_penguins()
    elif "diamond" in name_lower:
        return generate_diamonds()
    elif "air" in name_lower or "aqi" in name_lower:
        return generate_air_quality()
    elif "weather" in name_lower:
        return generate_weather()
    elif "retail" in name_lower or "sales" in name_lower:
        return generate_retail_sales()
    else:
        raise ValueError(f"Unknown sample dataset: {name}")
