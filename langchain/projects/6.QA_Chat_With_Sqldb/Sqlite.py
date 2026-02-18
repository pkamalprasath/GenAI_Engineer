import sqlite3

# Connect to Sqlite db
connection=sqlite3.connect("student.db")

# Create a cursor object to insert the record 
cursor=connection.cursor()

# Create a student table
table_info=""" create table STUDENT(NAME VARCHAR(25),CLASS VARCHAR(25),SECTION VARCHAR(25),MARKS INT)"""

connection.execute(table_info)

# Insert some records 
cursor.execute('''Insert Into STUDENT values('kamal','Data Science','A',90)''')
cursor.execute('''Insert Into STUDENT values('John','Data Science','B',100)''')
cursor.execute('''Insert Into STUDENT values('Mukesh','Data Science','A',86)''')
cursor.execute('''Insert Into STUDENT values('Jacob','DEVOPS','A',50)''')
cursor.execute('''Insert Into STUDENT values('Dipesh','DEVOPS','A',35)''')

print("The inserted record are ")
data=connection.execute("Select * from STUDENT")
for row in data: 
    print(row)

#Commit your changes 
connection.commit()
connection.close()
