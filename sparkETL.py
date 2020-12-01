import sys
import re
import nltk, nltk.stem.porter
from simplified_scrapy.simplified_doc import SimplifiedDoc 
from pyspark.sql import SparkSession, functions as f, types

sender_regex = r'From:[^<]+<([^\n]+)>'
receiver_regex = r'To: ([^\n]+)'
subject_regex = r'Subject: ([^\n]+)'
body_regex = r'\n\n([\H\n\s]*)'
date_regex = r'Date: +([^\n]+)'
length_regex = r'Content-Length: +([^\n]+'
cassandra_host = 'localhost'

def simplify_doc_udf(html_text):
	doc = SimplifiedDoc(html_text)
	return doc.text

def process_email_body(email_body):
    
    email_body = email_body.split("--", 1)
    
    #Removing non-ASCII characters results in a string that only contains ASCII characters.
    encoded_string = email_body[0].encode("ascii", "ignore")
    decode_string = encoded_string.decode()
    
    lower_string = decode_string.lower()
    #Looks for any expression that starts with < and ends with > and replace and does not have any < or > in the tag it with a space
    lower_string = re.sub('<[^<>]+>', ' ', lower_string)

    # Any numbers get replaced with the string 'number'
    lower_string = re.sub('[0-9]+', 'number', lower_string)

    # Anything starting with http or https:// replaced with 'httpaddr'
    lower_string = re.sub('(http|https)://[^\s]*', 'httpaddr', lower_string)

    # Strings with "@" in the middle are considered emails --> 'emailaddr'
    lower_string = re.sub('[^\s]+@[^\s]+', 'emailaddr', lower_string)

    # The '$' sign gets replaced with 'dollar'
    lower_string = re.sub('[$]+', 'dollar', lower_string)
    
    # Word list of email body
    word_list = re.split('[@$/#.-:&\*\+=\[\]?!(){},\'\'\">_<;%\s\n\r\t]+',lower_string.strip())
    
    stemmer = nltk.stem.porter.PorterStemmer()
    
    result_list = []
    for word in word_list:
        if len(word) >= 1:
            word = re.sub('[^a-zA-Z0-9]', '', word)
            word = stemmer.stem(word)
            result_list.append(word)
    #print(result_list)
        
    
def main(inputs, output):
	html_to_plain_udf = f.udf(simplify_doc_udf, types.StringType())
	raw_email = spark.read.text(inputs, wholetext = True)
	send_to_cassandra = raw_email.select(\
		f.regexp_extract('value', sender_regex, 1).alias('sender'), \
		f.regexp_extract('value', receiver_regex, 1).alias('receiver'), \
		f.regexp_extract('value', subject_regex, 1).alias('subject'), \
		f.regexp_extract('value', date_regex, 1).alias('date'), \
		f.regexp_extract('value', length_regex, 1).alias('word_length'), \
		f.regexp_extract('value', body_regex, 1).alias('html_body'))\
	.withColumn('id', f.monotonically_increasing_id())\
	.withColumn('body', html_to_plain_udf('html_body'))
    
    
    
    
	
	send_to_cassandra.select('id', 'sender', 'receiver', 'subject', 'body').write.csv(output, mode='overwrite')
	
	#send_to_cassandra.write.format("org.apache.spark.sql.cassandra")\
	#	.options(table = 'email', keyspace = 'email_database').save()
	
	
	
	
	
	
	
	
	
if __name__ == '__main__':
	inputs = sys.argv[1]
	output = sys.argv[2]
	spark = SparkSession.builder.appName('email ETL')\
		.config('spark.cassandra.connection.host', cassandra_host).getOrCreate()
	spark.sparkContext.setLogLevel('WARN')
	main(inputs, output)
