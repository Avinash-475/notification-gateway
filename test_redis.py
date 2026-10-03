import redis

r = redis.Redis(host='localhost' , port=6379 , decode_responses=True)

r.set('test_key','hello Redis')
value = r.get('test_key') 

print(value)

