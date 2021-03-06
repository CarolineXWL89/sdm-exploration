# -*- coding: utf-8 -*-
"""SDMWordModel.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1S1KqtorEqYzRFTSvAxRiK1cfCa3qVF-E

# Setting up the runtime with proper installations + virtual environment for python 3.7 (restart kernel after running this block)
"""

# Commented out IPython magic to ensure Python compatibility.
!python -m pip install --user virtualenv
!apt-get install python3.7
!apt-get install python3.7-venv
!python3.7 -m  venv env
!source env/bin/activate; pip install sdmlib; 
!pip install -U spacy
!spacy download en_vectors_web_lg
# %env PYTHONPATH=$PATH:/content/env/lib/python3.7/site-packages:/root/.local/bin
!echo $PATH

#restart kernel from here

"""# Data Pre-Processing"""

import sys
sys.path.append("/content/env/lib/python3.7/site-packages")
import numpy as np
import sdmlib
from sdmlib import Memory
import struct
import csv
import spacy
from sklearn.decomposition import PCA
n_components = 15

"""## Helper Functions """

#source: https://stackoverflow.com/questions/16444726/binary-representation-of-float-in-python-bits-not-hex
def to_bitstring(num):
    packed = struct.pack('!f', num)
    binaries = [bin(i) for i in packed]
    stripped_binaries = [s.replace('0b', '') for s in binaries]
    padded = [s.rjust(8, '0') for s in stripped_binaries]
    return ''.join(padded)

#turns a vector of real values into a binary vector
def vec_bin(vec):
    binary = []
    for v in vec:
        b = to_bitstring(v)
        binary.extend([int(s) for s in b])
    return binary

#writes dictionary to csv
def write_csv(dictionary, file):
  w = csv.writer(open(file, "w"))
  for key, val in dictionary.items():
    lst = [key]
    lst.extend(val)
    w.writerow(lst)

#reads dictionary from csv
def read_csv(file):
  vec_dictionary = {}
  r = csv.reader(open(file, "r"))
  for rows in r:
    vec_dictionary[rows[0].lower()] = np.asarray([int(s) for s in rows[1:]], dtype=np.uint8)
  return vec_dictionary

"""## Get word vectors from dataset and perform PCA"""

#get movie corpus from convokit: https://convokit.cornell.edu/documentation/movie.html
!pip install -U convokit
from convokit import Corpus, download
#corpus = Corpus(filename=download("movie-corpus"))
#trying another dataset
corpus = Corpus(filename=download("reddit-corpus-small"))

import re

text = ""
length = 0
for utt in corpus.iter_utterances():
  convo = utt.text
  convo = convo.replace("\"", "").replace(".", "").replace(",", "").replace("?", "").replace("!", "")
  # convo = convo.replace("[\".;!,:']", "")
  # convo = re.sub(r'\b[.!,?;:]\b', ' \g<0> ', convo)
  # convo = re.sub(r'\B[.!,?;:]\b', ' \g<0> ', convo)
  # convo = re.sub(r'\b[.!,?;:]\B', ' \g<0> ', convo)
  convo = convo.lower().split()
  length += len(convo)
  text += " " + ' '.join(convo)

  #this is for computation sake
  if length > 150000:
    break

#load in spacy vector package of word vectors
nlp = spacy.load("en_vectors_web_lg")
tokens = nlp(text)

#put all vectors in ndarray
X = tokens[0].vector
seen = [tokens[0].text]
for i in range(1, len(tokens)):
  if (tokens[i].has_vector) and (tokens[i].vector_norm != 0) and (tokens[i].text not in seen):
    X = np.vstack((X, tokens[i].vector))
    seen.append(tokens[i].text)

#perform PCA to reduce dimensions from 300 to 30
#if this is too costly for the SDM, lower n_components (and check to make sure the vectors are still unique)
print("Performing PCA...")
pca = PCA(n_components=n_components)
X_hat = pca.fit_transform(X)
print("PCA Complete! Dimensions of X are now ", (X_hat.shape))

"""## Write bitstring to csv to save our RAM"""

threshold = np.mean(X)
X_bool = X > threshold
X_bool = np.array(X_bool, dtype=np.uint8)

word2vec_bool = {}
for i in range(X_bool.shape[0]):
    word2vec_bool[seen[i]] = X_bool[i]
    
write_csv(word2vec_bool, "word2vec_bool.csv")

#convert vectors to bitstrings (15*32 dimensions) and create dictionary of (word, binary vectors)
word2vec = {}
for i in range(X_hat.shape[0]):
    word2vec[seen[i]] = vec_bin(X_hat[i])

#write to csv (this isn't super needed anymore, but in case we want it it's here)
write_csv(word2vec, "word2vec.csv")

#save dataset
text_file = open("dataset.txt", "w")
text_file.write(text)
text_file.close()

"""## Read in vectors from CSV"""

word2vec_bool = read_csv("word2vec_bool.csv")
vec2word_bool = {}
for key, val in word2vec_bool.items():
  bitstring = ''.join([str(v) for v in val])
  if (bitstring in vec2word_bool.keys()):
    print("These two words have the same vector: ", key, vec2word_bool[bitstring])
  vec2word_bool[bitstring] = key

word2vec = read_csv("word2vec.csv")

#create vec->word dictionary
vec2word = {}
for key, val in word2vec.items():
  bitstring = ''.join([str(v) for v in val])
  if (bitstring in vec2word.keys()):
    print("These two words have the same vector: ", key, vec2word[bitstring])
  vec2word[bitstring] = key

#word2vec and vec2word are essentially the same thing (just one has the word as the key and the other the bitstring)
#word2vec stores the vector as a list of ints
#vec2word stores the vector (the key) as a bitstring

"""#Training

## Helper Functions
"""

import pickle 
def vec2bitstring(vec):
    bitstring = vec
    if not isinstance(vec, str):
      vec_list = [str(bit) for bit in vec.tolist()]
      bitstring = ''.join(vec_list)
    return bitstring

def hamming(vec1, word2vec):
    min_dist = float('inf')
    best_vec = None
    for key, vec in word2vec.items():
        hamming_dist = np.sum(np.bitwise_xor(vec1, vec))
        if hamming_dist < min_dist:
            best_vec = vec
            min_dist = hamming_dist
    # print(f"hamming: {min_dist}")
    return best_vec

def store_model(db):
    dbfile = open('model', 'ab') 
    # source, destination 
    pickle.dump(db, dbfile)                      
    dbfile.close() 

def load_model():
    dbfile = open('model', 'rb')      
    db = pickle.load(dbfile) 
    dbfile.close()
    return db 

def generate_scramble():
    static_seed = np.random.randint(1000000)
    return lambda x: np.random.RandomState(seed=static_seed).permutation(x)

def history(word, prev_H, scramble, a, b):
    num_bits = address_length if word is None else word.shape[0]
    # print("num bits: ", num_bits)
    cutoff = int(a*num_bits)
    # print("cutoff: ", cutoff)
    sprev_H = scramble(prev_H)
    # print("scrambled history: ", len(sprev_H))
    H = np.hstack((word[:cutoff], sprev_H[cutoff:]))
    return np.asarray(H, dtype=np.uint8)

def history_seq(word_seq, prev_H, scramble, a, b):
    h = []
    for word in word_seq:
        # print(type(word))
        #if word is None:
        # continue
        prev_H = history(word, prev_H, scramble, a, b)
        h.append(prev_H)
    return h

def write(word, next_word, prev_H, scramble, a, b, unknown):
    H = history(word, prev_H, scramble, a, b)
    # print("H", H.shape)
    # print("word ", np.asarray(word).shape)
    if unknown:
        next_word = H
    mem.write(H, next_word)
    bitstring=vec2bitstring(next_word)
    # print(vec2word.get(bitstring))
    read_bitstr = read(H, scramble, a, b, 1)
    # print(read_bitstr)
    return H

#"The dog barked at the cat"

#"The" read H = (The, 000000000, scramble, a, b)
#lol not done
#"The dog" --> H
def read(prev_H, scramble, a, b, num_words):
    word_seq=[]
    for i in range(num_words):
        word = mem.read(prev_H)
        bitstring = vec2bitstring(word)
        if bitstring not in vec2word:
            word = hamming(word, word2vec)
            # print(type(word))
            temp_bitstr = vec2word.get(vec2bitstring(word))
            word_seq.append(temp_bitstr if type(word) is np.ndarray or temp_bitstr else "unknown_word")            
        else:
            word_seq.append(vec2word.get(bitstring))
        prev_H = history(word, prev_H, scramble, a, b)
    return " ".join(word_seq)

import time
#training:
# Set weights for history function
scramble = generate_scramble()
a = 0.25
b = 1 - a

#set up memory space
address_length = len(word2vec['the'])
N = address_length
M = 1000000
U = address_length
T = 11000

mem = Memory(N=N, M=M, U=U, d=None, T=T)
fileObject = open("dataset.txt", "r")
data = fileObject.read().split()

start_H = np.zeros(address_length, dtype=np.uint8)
prev_H = start_H
unknown_words = []
punctuation = ['.', '?', '!', ';']

start = time.perf_counter()
for i in range(T):
    unknown = False
    got_data = data[i+1] in word2vec

    #I think we should set the word vector to be = H for unknown words? but we would have to make sure it's unique...
    #for now, making a list of unknown words
    if got_data:
        next_word = word2vec.get(data[i+1])
    else:
        next_word = np.zeros(address_length, dtype=np.uint8)
        unknown_words.append(data[i+1])
        unknown = True

    got_data = data[i] in word2vec
    if got_data and data[i].strip() in punctuation:
        # print(f"data[i]: {data[i]}; got_data: {got_data}")
        prev_H = start_H
        continue
    # print("not punctuation")
    word = word2vec.get(data[i]) if got_data else np.zeros(address_length, dtype=np.uint8)
    prev_H = write(word, next_word, prev_H, scramble, a, b, unknown)

    if unknown:
      word2vec[data[i+1]] = prev_H
      bitstring = ''.join([str(b) for b in prev_H])
      vec2word[bitstring] = data[i+1]
    if (i%1000 == 0):
        end = time.perf_counter()
        print(f"{i} iteration completed in {end - start:0.4f} seconds")
store_model(mem)

#store_model(mem)
mem = load_model()

#generating sequences
import random 

tester_input = [] 
text_file = open("dataset.txt", "r").readlines()[0]
words = text_file.lower().replace("\"", "").replace(".", "").replace(",", "").replace("?", "").replace("!", "").split()
for _ in range(20):
  word = random.choice(words)
  # print(word)
  if word not in tester_input:
    tester_input.append(word)

print(tester_input)
prev_H = np.zeros(address_length)
tester_vectors = [word2vec.get(w.lower()) for w in tester_input]
histories = history_seq(tester_vectors, prev_H, scramble, a, b)
for i in range(len(tester_input)):
    #turn word into vector
    word = read(histories[i], scramble, a, b, len(tester_input))
    # print(f"histories: {histories}")
    print(f"{tester_input[i]}: {word}")

"""# Testing"""

import re
text = []
length = 0
for utt in corpus.iter_utterances():
  convo = utt.text
  convo = convo.lower().split()
  length += len(convo)
  text.extend(convo)

text = ' '.join(text)
#obtain sentences from the dataset
pat = re.compile(r'([a-z][^\.!?;]*[\.!?])', re.M)
sentences = pat.findall(text)

import math
prev_H = np.zeros(address_length)
sample = random.sample(sentences, 20)
for s in sample:
  s = s.replace("\"", "").replace(".", "").replace(",", "").replace("?", "").replace("!", "")

  s = s.lower()
  print("Original sentence: ", s)
  s = s.split()
  s_vec = [word2vec.get(w.lower()) for w in s]
  if len(s_vec) < 3:
    continue
  histories = history_seq(s_vec, prev_H, scramble, a, b)

  #predict the rest of the sentence given the first third
  print("generate the rest of the sentence given the first third of the sentence:")
  third_len = int(math.floor(0.3*len(s_vec)))
  third_test = s_vec[:third_len]
  h = histories[third_len-1]
  word = read(h, scramble, a, b, len(s)-third_len)
  start = ' '.join(s[:third_len])
  print(f"{start}: {word}") len(s_vec)-twothird_len)  
  start = ' '.join(s[:twothird_len])
  print(f"{start}: {word}")
  print("\n")
  print()

  #predict the rest of the sentence given the first half
  print("generate the rest of the sentence given the first half of the sentence:")
  half_len = int(math.floor(0.5*len(s_vec)))
  half_test = s_vec[:half_len]
  h = histories[half_len-1]
  word = read(h, scramble, a, b, len(s_vec)-half_len)  
  start = ' '.join(s[:half_len])
  print(f"{start}: {word}")
  print()

  #predict the rest of the sentence given the first half
  print("generate the rest of the sentence given the first two-thirds of the sentence:")
  twothird_len = 2*third_len
  half_test = s_vec[:twothird_len]
  h = histories[twothird_len-1]
  word = read(h, scramble, a, b,

"""## Corpus Analytics

"""

#https://towardsdatascience.com/very-simple-python-script-for-extracting-most-common-words-from-a-story-1e3570d0b9d0
import collections
file = open('dataset.txt', encoding="utf8")
a= file.read().lower().split()[:11000]

# Instantiate a dictionary, and for every word in the file, 
# Add to the dictionary if it doesn't exist. If it does, increase the count.
wordcount = {}
# To eliminate duplicates, remember to split by punctuation, and use case demiliters.
for word in a:
    word = word.replace(".","")
    word = word.replace(",","")
    word = word.replace(":","")
    word = word.replace("\"","")
    word = word.replace("!","")
    word = word.replace("â€œ","")
    word = word.replace("â€˜","")
    word = word.replace("*","")
    if word not in wordcount:
        wordcount[word] = 1
    else:
        wordcount[word] += 1
# Print most common word
n_print = int(input("How many most common words to print: "))
print("\nOK. The {} most common words are as follows\n".format(n_print))
word_counter = collections.Counter(wordcount)
for word, count in word_counter.most_common(n_print):
    print(word, ": ", count)
# Close the file
file.close()

