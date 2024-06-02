import numpy as np
import chromadb
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain.llms import LlamaCpp
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.prompts import PromptTemplate
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.chains.question_answering import load_qa_chain
from langchain.output_parsers import CommaSeparatedListOutputParser
from semantic_router.layer import RouteLayer

#Extraction
import re
from nltk.corpus import words
from unidecode import unidecode
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.corpus import wordnet

import BRAD.gene_ontology as gonto
from BRAD.gene_ontology import geneOntology

def queryDocs(chatstatus):
    """
    Query the RAG database and interact with the llama model.

    This function queries the RAG (Related Articles Generator) database using 
    the user's prompt, obtains relevant documents and their relevance scores, 
    passes them to the llama-2 language model (LLM) for question answering, 
    processes the LLm output, updates the chat status, and returns the updated 
    chat status.

    Args:
        chatstatus (dict): The current status of the chat, including the LLM 
                           instance, user prompt, RAG database instance, and 
                           other metadata.

    Returns:
        dict: The updated chat status, including the LLm output text, LLm process 
              information, and any additional metadata.

    Notes:
        - The function uses the LLM to answer questions based on the retrieved 
          documents.
        - It updates the chat status with the LLm's output text, process information, 
          and any relevant metadata.
        - The function interacts with the RAG database and may call additional 
          functions, such as `getDocumentSimilarity` and `geneOntology`, to process 
          the retrieved documents.

    Example:
        # Query the RAG database and interact with the llama model
        chatstatus = {
            'llm': llama_model_instance,
            'prompt': "What is the latest research on COVID-19?",
            'databases': {'RAG': ragvectordb_instance},
            'output': None,
            'process': {}
        }
        updated_chatstatus = queryDocs(chatstatus)
    """
    process = {}
    llm      = chatstatus['llm']              # get the llm
    prompt   = chatstatus['prompt']           # get the user prompt
    vectordb = chatstatus['databases']['RAG'] # get the vector database
    
    # query to database
    documentSearch = vectordb.similarity_search_with_relevance_scores(prompt)
    docs, scores = getDocumentSimilarity(documentSearch)

    # pass the database output to the llm
    chain = load_qa_chain(llm, chain_type="stuff")
    res = chain({"input_documents": docs, "question": prompt})
    print(res['output_text'])

    # change inputs to be json readable
    res['input_documents'] = getInputDocumentJSONs(res['input_documents'])

    # update and return the chatstatus
    chatstatus['output'], chatstatus['process'] = res['output_text'], res
    chatstatus = geneOntology(chatstatus['output'], chatstatus)
    return chatstatus

def getPreviousInput(log, key):
    """
    Retrieve previous input or output text from the chat log.

    This function retrieves and returns either the previous user input or the 
    output text from the chat log, based on the provided key.

    Warnings:
        This function is in the process of being depricated.

    Args:
        log (dict): The chat log dictionary containing previous chat entries.
        key (str): The key indicating which previous input or output to retrieve. 
                   It should be in the format 'nI' or 'nO', where 'n' is an integer 
                   representing the index in the log, and 'I' or 'O' specifies 
                   whether to retrieve the input or output text.

    Returns:
        str: The previous input text if 'key' ends with 'I', or the previous output 
             text if 'key' ends with 'O'.

    Notes:
        - The 'log' parameter should be a dictionary where keys are integers 
          representing chat session indices, and values are dictionaries containing 
          'prompt' (input) and 'output' (output) keys.

    Example:
        # Retrieve previous input text from the chat log
        log = {
            1: {'prompt': 'What is the weather today?', 'output': 'The weather is sunny.'},
            2: {'prompt': 'Tell me about COVID-19.', 'output': 'COVID-19 is caused by...'}
        }
        key = '1I'
        previous_input = getPreviousInput(log, key)  # returns 'What is the weather today?'

        # Retrieve previous output text from the chat log
        key = '2O'
        previous_output = getPreviousInput(log, key)  # returns 'COVID-19 is caused by...'
    """
    num = key[:-1]
    text = key[-1]
    if text == 'I':
        return log[int(num)][text]
    else:
        return log[int(num)][text]['output_text']
    
def getInputDocumentJSONs(input_documents):
    """
    Convert a list of input documents into a JSON-compatible format.

    This function iterates through a list of input documents, extracts 
    relevant information (page content and source metadata), and returns 
    a dictionary where each document is represented as a JSON object.

    Args:
        input_documents (list): A list of input documents, each containing 
                                page content and metadata.

    Returns:
        dict: A dictionary where each key is an index and each value is a 
              JSON object representing a document, containing 'page_content' 
              and 'metadata'.

    Notes:
        - Each input document should be an object with attributes 'page_content' 
          and 'metadata', where 'metadata' is a dictionary containing at least 
          a 'source' key.

    Example:
        # Convert input documents to JSON-compatible format
        input_documents = [
            {'page_content': 'Document text 1.', 'metadata': {'source': 'PubMed'}},
            {'page_content': 'Document text 2.', 'metadata': {'source': 'arXiv'}}
        ]
        input_docs_json = getInputDocumentJSONs(input_documents)
        # input_docs_json would be:
        # {
        #     0: {'page_content': 'Document text 1.', 'metadata': {'source': 'PubMed'}},
        #     1: {'page_content': 'Document text 2.', 'metadata': {'source': 'arXiv'}}
        # }
    """
    inputDocsJSON = {}
    for i, doc in enumerate(input_documents):
        inputDocsJSON[i] = {
            'page_content' : doc.page_content,
            'metadata'     : {
                'source'   : doc.metadata['source']
            }
        }
    return inputDocsJSON

def getDocumentSimilarity(documents):
    """
    Extract documents and their similarity scores from a list of tuples.

    This function extracts the documents and their similarity scores from 
    a list of tuples and returns them separately.

    Args:
        documents (list): A list of tuples, where each tuple contains a 
                          document and its similarity score.

    Returns:
        tuple: A tuple containing:
            - list: The list of documents.
            - numpy.ndarray: An array of similarity scores.

    Notes:
        - Each tuple in the 'documents' list should be in the format (document, score).
        - The function separates the documents and scores into two separate lists.

    Example:
        # Extract documents and scores from a list of tuples
        documents = [
            ('Document 1 text.', 0.85),
            ('Document 2 text.', 0.78),
            ('Document 3 text.', 0.92)
        ]
        docs, scores = getDocumentSimilarity(documents)
        # docs would be: ['Document 1 text.', 'Document 2 text.', 'Document 3 text.']
        # scores would be: array([0.85, 0.78, 0.92])
    """
    scores = []
    docs   = []
    for doc in documents:
        docs.append(doc[0])
        scores.append(doc[1])
    return docs, np.array(scores)

# Define a function to get the wordnet POS tag
def get_wordnet_pos(word):
    """
    Map POS tag to first character lemmatize() accepts.

    This function maps a Part-Of-Speech (POS) tag to the first character 
    that the WordNetLemmatizer in NLTK accepts for lemmatization.

    Args:
        word (str): A word for which the POS tag needs to be mapped.

    Returns:
        str: The corresponding WordNet POS tag.

    Notes:
        - This function uses NLTK's `pos_tag` function to get the POS tag 
          of the input word.
        - It maps POS tags to WordNet's POS tag format for lemmatization.

    Example:
        # Get WordNet POS tag for a word
        word = "running"
        pos_tag = get_wordnet_pos(word)  # returns 'v' for verb
    """
    tag = nltk.pos_tag([word])[0][1][0].upper()
    tag_dict = {"J": wordnet.ADJ,
                "N": wordnet.NOUN,
                "V": wordnet.VERB,
                "R": wordnet.ADV}
    return tag_dict.get(tag, wordnet.NOUN)

def extract_non_english_words(text):
    """
    Extract non-English words from a given text.

    This function extracts words from the given text, lemmatizes them, filters 
    out English words using a set of English words and a custom word list, and 
    returns non-English words.

    Args:
        text (str): The input text from which non-English words need to be extracted.

    Returns:
        list: A list of non-English words extracted from the input text.

    Notes:
        - English words are filtered out using a set of words from NLTK's words 
          corpus and a custom word list.
        - The function uses NLTK's WordNetLemmatizer and part-of-speech tagging.
        - The input text is normalized to ASCII using the unidecode library.

    Example:
        # Extract non-English words from a text
        text = "The pluripotency of stem cells in biology is fascinating."
        non_english_words = extract_non_english_words(text)
        # non_english_words would be: ['pluripotency', 'biology', 'genomics', 'reprogramming']
    """
    # Set of English words
    custom_word_list = ["pluripotency", "differentiation", "stem", "cell", "biology", "genomics", "reprogramming"]
    english_words = set(words.words()+custom_word_list)
    # Normalize text to ASCII
    normalized_text = unidecode(text)
    
    # Extract words from the text using regex
    word_list = re.findall(r'\b\w+\b', normalized_text.lower())
    
    lemmatizer = WordNetLemmatizer()
    lemmatized_words = [lemmatizer.lemmatize(word, get_wordnet_pos(word)) for word in word_list]
    filtered_words = [word for word in lemmatized_words if not word.isnumeric()]
    
    # Filter out English words
    non_english_words = [word for word in filtered_words if word not in english_words]
    
    return non_english_words


