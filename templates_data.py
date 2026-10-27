"""Predefined itinerary templates. Costs are illustrative estimates (INR) for a party of 2; not live prices.
Activity tuple: (day_number, 'HH:MM', name, location, estimated_cost)"""
TEMPLATES = [
 dict(slug="jaipur-city", title="Jaipur City Exploration", category="City Exploration", destination="Jaipur, Rajasthan", days=3, budget=26000,
  desc="Forts, palaces and bazaars of the Pink City at an easy pace.", acts=[
  (1,"09:00","Amber Fort visit","Amber Fort",1000),(1,"13:00","Rajasthani thali lunch","Johari Bazaar",800),(1,"16:00","Hawa Mahal and bazaar walk","Hawa Mahal",500),
  (2,"09:30","City Palace tour","City Palace",1000),(2,"12:30","Jantar Mantar observatory","Jantar Mantar",400),(2,"17:00","Sunset at Nahargarh Fort","Nahargarh Fort",600),
  (3,"10:00","Albert Hall Museum","Albert Hall Museum",300),(3,"12:00","Block-printing workshop","Sanganer",1500),(3,"16:00","Souvenir shopping","Bapu Bazaar",2000)]),
 dict(slug="lonavala-weekend", title="Lonavala Weekend Getaway", category="Weekend Getaway", destination="Lonavala, Maharashtra", days=2, budget=14000,
  desc="A short monsoon-friendly escape with viewpoints, caves and a fort hike.", acts=[
  (1,"10:00","Bhushi Dam and waterfalls","Bhushi Dam",200),(1,"13:30","Local Maharashtrian lunch","Lonavala Market",800),(1,"15:30","Karla and Bhaja Caves","Karla Caves",400),(1,"18:30","Sunset at Tiger Point","Tiger Point",300),
  (2,"08:00","Lohagad Fort hike","Lohagad Fort",600),(2,"12:30","Brunch","Khandala",700),(2,"15:00","Chikki shopping and return","Lonavala Market",500)]),
 dict(slug="goa-beach", title="Goa Beach Holiday", category="Beach Holiday", destination="Goa", days=4, budget=38000,
  desc="Beaches, water sports, heritage churches and seafood.", acts=[
  (1,"11:00","Sunbeds and beach time","Calangute Beach",300),(1,"17:30","Water sports","Baga Beach",2000),(1,"20:00","Beach shack dinner","Baga Beach",1800),
  (2,"09:00","Old Goa churches","Basilica of Bom Jesus",300),(2,"13:00","Latin Quarter walk","Fontainhas, Panaji",400),(2,"18:00","Mandovi river cruise","Panaji Jetty",800),
  (3,"08:30","Dolphin-spotting boat trip","Sinquerim",1200),(3,"12:00","Fort Aguada","Fort Aguada",100),(3,"16:00","Beach cafes","Anjuna Beach",1000),
  (4,"09:00","Kayaking","Palolem Beach",1500),(4,"13:00","Seafood lunch","Palolem Beach",1500)]),
 dict(slug="manali-hills", title="Manali Hill Station Escape", category="Hill Station", destination="Manali, Himachal Pradesh", days=4, budget=42000,
  desc="Mountain views, snow-side activities and old-town cafes.", acts=[
  (1,"14:00","Hadimba Temple","Hadimba Temple",100),(1,"16:00","Mall Road walk","Mall Road",500),(1,"19:30","Dinner at cafes","Old Manali",1500),
  (2,"08:00","Solang Valley activities","Solang Valley",2500),(2,"13:00","Atal Tunnel and Sissu drive","Atal Tunnel",1500),(2,"18:00","Bonfire evening","Camp site",800),
  (3,"09:00","Naggar Castle and Roerich Gallery","Naggar",600),(3,"13:00","Jogini Waterfall trek","Vashisht",300),(3,"17:00","Hot springs","Vashisht",100),
  (4,"09:00","River rafting","Beas River, Kullu",1200),(4,"13:30","Himachali lunch","Mall Road",700)]),
 dict(slug="agra-delhi-heritage", title="Agra and Delhi Historical Tour", category="Historical Tour", destination="Agra and Delhi", days=3, budget=30000,
  desc="Mughal monuments from the Taj Mahal to the Red Fort.", acts=[
  (1,"06:00","Taj Mahal at sunrise","Taj Mahal, Agra",1000),(1,"10:00","Agra Fort","Agra Fort",600),(1,"15:00","Sunset at Mehtab Bagh","Mehtab Bagh",300),
  (2,"09:00","Fatehpur Sikri","Fatehpur Sikri",500),(2,"14:00","Drive to Delhi (tolls and fuel share)","Yamuna Expressway",1500),(2,"19:00","Mughlai dinner","Jama Masjid, Delhi",900),
  (3,"09:00","Red Fort","Red Fort, Delhi",600),(3,"11:30","Humayun's Tomb","Humayun's Tomb",600),(3,"15:00","Qutub Minar","Qutub Minar",600),(3,"17:30","Evening walk","India Gate",0)]),
 dict(slug="rishikesh-adventure", title="Rishikesh Adventure Break", category="Nature & Adventure", destination="Rishikesh, Uttarakhand", days=3, budget=22000,
  desc="River rafting, bungee and riverside yoga in the Himalayan foothills.", acts=[
  (1,"11:00","Jhula bridges walk","Laxman Jhula",100),(1,"18:00","Ganga Aarti","Triveni Ghat",0),
  (2,"07:30","White-water rafting (16 km)","Shivpuri",1500),(2,"12:30","Riverside camp lunch","Shivpuri",600),(2,"16:00","Bungee jump","Mohanchatti",3500),
  (3,"06:00","Neelkanth Mahadev trek","Neelkanth Trail",1000),(3,"14:00","Yoga session","Parmarth Niketan",500)]),
 dict(slug="mumbai-food", title="Mumbai Food Trail", category="Food Trip", destination="Mumbai, Maharashtra", days=2, budget=16000,
  desc="Irani cafes, street food and seafood across the city.", acts=[
  (1,"08:30","Irani cafe breakfast","South Mumbai",400),(1,"12:00","Vada pav and street-food crawl","Girgaon Chowpatty",600),(1,"21:00","Kebab night","Mohammed Ali Road",1000),
  (2,"10:00","Food walk","Colaba Causeway",700),(2,"14:00","Seafood thali lunch","Fort",1500),(2,"18:00","Chaat and pav bhaji","Juhu Beach",500)]),
 dict(slug="kerala-backwaters", title="Kerala Backwaters Relaxation", category="Relaxing Vacation", destination="Alappuzha and Kochi, Kerala", days=4, budget=45000,
  desc="Houseboat cruise, ayurvedic wellness and slow village life.", acts=[
  (1,"16:00","Sunset at the beach","Alappuzha Beach",100),(1,"19:00","Ayurvedic massage","Alappuzha",2500),
  (2,"10:00","Houseboat cruise (overnight)","Vembanad Lake",9000),(2,"17:00","Village canoe ride","Kuttanad",600),
  (3,"09:00","Bird sanctuary visit","Kumarakom",300),(3,"13:00","Karimeen fish lunch","Kumarakom",1200),(3,"17:00","Kathakali performance","Kochi",500),
  (4,"10:00","Heritage walk","Fort Kochi",300),(4,"14:00","Fishing nets and spice market","Fort Kochi",400)]),
 dict(slug="mysuru-family", title="Mysuru Family Vacation", category="Family Vacation", destination="Mysuru, Karnataka", days=3, budget=28000,
  desc="Palaces, a zoo, gardens and a river bird sanctuary that suit all ages.", acts=[
  (1,"10:00","Mysore Palace tour","Mysore Palace",500),(1,"15:00","Chamundi Hills","Chamundi Hills",300),(1,"18:30","Musical fountain","Brindavan Gardens",400),
  (2,"09:30","Zoo visit","Mysuru Zoo",600),(2,"13:00","Butterfly park","Karanji Lake",200),(2,"16:00","Shopping and church visit","Devaraja Market",1500),
  (3,"08:00","Tipu Sultan heritage sites","Srirangapatna",300),(3,"11:00","Boat ride","Ranganathittu Bird Sanctuary",700),(3,"14:00","Picnic","KRS Dam",400)]),
 dict(slug="udaipur-sightseeing", title="Udaipur Lakes and Palaces", category="Sightseeing", destination="Udaipur, Rajasthan", days=3, budget=32000,
  desc="Lakeside palaces, temples and a day trip to hill forts.", acts=[
  (1,"10:00","City Palace complex","City Palace",700),(1,"15:30","Lake Pichola boat ride","Lake Pichola",600),(1,"19:00","Lakeside rooftop dinner","Lake Pichola",2500),
  (2,"09:00","Jagdish Temple","Jagdish Temple",0),(2,"11:00","Garden visit","Saheliyon ki Bari",100),(2,"16:00","Sunset viewpoint","Fateh Sagar Lake",200),(2,"19:00","Folk dance show","Bagore Ki Haveli",400),
  (3,"08:00","Kumbhalgarh Fort excursion","Kumbhalgarh",1500),(3,"14:00","Ranakpur Jain Temple","Ranakpur",1200)]),
]
