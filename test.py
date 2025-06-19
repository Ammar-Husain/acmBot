from dotenv import dotenv_values

from methods.mongo import connect_to_mongo

client = connect_to_mongo(dotenv_values()["DB_URI"])

users = client.acmbDB.users.find({})
print(users)

for user in users:
    print(user)
