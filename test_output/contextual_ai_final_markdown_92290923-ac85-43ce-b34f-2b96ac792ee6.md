
--- Page 0 ---

[FIGURE_CAPTION START]
**High level description**
The image contains the logo of the company "weaviate". The logo consists of a stylized "W" symbol in yellow and green, followed by the company name spelled out in white letters. The background is a dark blue color.
[FIGURE_CAPTION END]

# Advanced RAG Techniques

A guide on different techniques to improve the performance of your Retrieval-Augmented Generation applications.


--- Page 1 ---

Retrieval-augmented generation (RAG) provides generative large language models (LLMs) with information from an external knowledge source to help reduce hallucinations and increase the factual accuracy of the generated responses.

A naive RAG pipeline consists of four components: an embedding model, a vector database, a prompt template, and a generative LLM. At inference time, it embeds the user query to retrieve relevant document chunks of information from the vector database, which it stuffs into the LLM’s prompt to generate an answer.

[FIGURE_CAPTION START]
**High level description**
The image presents a table that outlines optimization techniques for a RAG pipeline at different stages. The stages are Indexing, Pre-retrieval, Retrieval, and Post-retrieval. Each stage has a corresponding page number in the document where the optimization techniques are discussed in detail. The page numbers are: Indexing (3), Pre-retrieval (5), Retrieval (7), and Post-retrieval (10).

**Key data points**
- Indexing Optimization Techniques: 3
- Pre-retrieval Optimization Techniques: 5
- Retrieval Optimization Strategies: 7
- Post-retrieval Optimization Techniques: 10
[FIGURE_CAPTION END]

While this naive approach is straightforward, it has many limitations and can often lead to low- quality responses.

This e-book discusses various advanced techniques you can apply to improve the performance of your RAG system. These techniques can be applied at various stages in the RAG pipeline, as shown below:


--- Page 2 ---

[FIGURE_CAPTION START]
**High level description**
The flowchart depicts the RAG pipeline, starting with "Documents" which are then processed into "Chunks". A "Query" is input and transformed by an "Embedding Model", which interacts with a "Vector Database" to retrieve relevant "Context". A "Prompt Template" combines the query and context, and this is fed into an "LLM" to generate a "Response". The flow is represented by arrows indicating the sequence of operations in the RAG pipeline.
[FIGURE_CAPTION END]

## Indexing Optimization Techniques

Index optimization techniques enhance retrieval accuracy by structuring external data in more organized, searchable ways. These techniques can be applied to both data pre-processing and chunking stages in the RAG pipeline, ensuring that relevant information is effectively retrieved.

### Data Pre-Processing

Data pre-processing is fundamental to the success of any RAG system, as the quality of your processed data directly impacts the overall performance. By thoughtfully transforming raw data into a structured format suitable for LLMs, you can significantly enhance your system's effectiveness before considering more complex optimizations.

While there are several common pre-processing techniques available, the optimal approach and sequence should be tailored to your specific use case and requirements.

The process usually begins with data acquisition and integration, where diverse document types from multiple sources are collected and consolidated into a ‘knowledge base’.

[FIGURE_CAPTION START]
**Figure title**
Data Sources

**High level description**
The diagram shows three data sources labeled as 'Source 1', 'Source 2', and 'Source 3'. Each source has a line connecting it to a 'Raw Data' container. The diagram illustrates a simple data pipeline where data from multiple sources is aggregated into a single raw data repository.
[FIGURE_CAPTION END]

### Data Extraction and Data Parsing

Data extraction and parsing take place over the raw data so that it is accurately processed for downstream tasks. For text-based formats like Markdown, Word documents, and plain text, extraction techniques focus on preserving structure while capturing relevant content.

Scanned documents, images, and PDFs containing image-based text/tables require OCR (Optical Character Recognition) technology to convert into an ‘LLM-ready’ format. However, recent advancements in multimodal retrieval models, such as ColPali and ColQwen, have revolutionized this process. These models can directly embed images of documents, potentially making traditional OCR obsolete.

Web content often involves HTML parsing, utilizing DOM traversal to extract structured data, while spreadsheets demand specialized parsing to handle cell relationships. Metadata extraction is also crucial across file types, pulling key details like author, timestamps, and other document properties (see Metadata Filtering)


--- Page 3 ---

### Data Cleaning

Data cleaning and noise reduction involves removing irrelevant information (such as headers, footers, or boilerplate text), correcting inconsistencies, and handling missing values while maintaining the extracted data's structural integrity.

[FIGURE_CAPTION START]
**High level description**
The diagram illustrates the data cleaning process, starting with "Raw Data", which undergoes "Data Extraction + Data Parsing" to become "Parsed Data". Subsequently, "Data Cleaning + Noise Reduction" are applied to transform the "Parsed Data" into "Cleansed Data". The diagram uses icons of documents to represent the data at each stage, with the "Cleansed Data" icon having sparkle effects to indicate cleanliness.
[FIGURE_CAPTION END]

### Data Transformation

This involves converting all extracted and processed content into a standardized schema, regardless of the original file type. It's at this stage that document partitioning (not to be confused with chunking) occurs, separating document content into logical units or elements (e.g., paragraphs, sections, tables)

[FIGURE_CAPTION START]
**High level description**
The diagram illustrates a data processing pipeline with three stages: Cleansed Data, Transformed Data, and Data Chunks. The process of transforming data from Cleansed Data to Transformed Data is labeled as "Data Transformation". The process of converting Transformed Data into Data Chunks is labeled as "Chunking". The diagram uses stacks of green rectangles to represent the data at each stage, with different patterns indicating the state of the data.
[FIGURE_CAPTION END]

### Chunking Strategies

Chunking divides large documents into smaller, semantically meaningful segments. This process optimizes retrieval by balancing context preservation with manageable chunk sizes. Various common techniques exist for effective chunking in RAG, some of which are discussed below:

Fixed-size chunking is a simple technique that splits text into chunks of a predetermined size, regardless of content structure. While it's cost-effective, it lacks contextual awareness. This can be improved by using overlapping chunks, allowing adjacent chunks to share some content.

[FIGURE_CAPTION START]
**High level description**
The diagram illustrates the concept of overlapping chunks. The sentence "Photosynthesis is one of nature's most vital processes." is divided into three chunks labeled "chunk 1", "chunk 2", and "chunk 3". There are overlaps between "chunk 1" and "chunk 2", and between "chunk 2" and "chunk 3", as indicated by the "overlap" labels.
[FIGURE_CAPTION END]

Recursive chunking offers more flexibility by initially splitting text using a primary separator (like paragraphs) and then applying secondary separators (like sentences) if chunks are still too large. This technique respects the document's structure and adapts well to various use cases.

[FIGURE_CAPTION START]
**High level description**
The image presents a textual description of quantum entanglement. It defines quantum entanglement as a key concept in quantum physics, occurring when particles become linked such that the state of one instantly affects the state of another, regardless of the distance between them. The text also mentions that measuring one entangled particle causes the other's state to change instantly, challenging our understanding of space and time.
[FIGURE_CAPTION END]

Document-based chunking creates chunks based on the natural divisions within a document, such as headings or sections. It's particularly effective for structured data like HTML, Markdown, or code files but less useful when the data lacks clear structural elements.

[FIGURE_CAPTION START]
**High level description**
The image provides examples of headings and subheadings, demonstrating how document content can be structured. The first example shows a heading denoted by '# Heading', followed by the text 'This is a heading.'. The second example shows a subheading denoted by '## Subheading', followed by the text 'This is a subheading. We can continue withmore content here.'

**Key data points**
- # Heading This is a heading.
- ## Subheading This is a subheading. We can continue withmore content here.
[FIGURE_CAPTION END]

Semantic chunking divides text into meaningful units, which are then vectorized. These units are then combined into chunks based on the cosine distance between their embeddings, with a new chunk formed whenever a significant context shift is detected. This method balances semantic coherence with chunk size.

LLM-based chunking is an advanced technique that uses an LLM to generate chunks by processing text and creating semantically isolated sentences or propositions. While highly accurate, it's also the most computationally demanding approach.

[FIGURE_CAPTION START]
**High level description**
The diagram illustrates LLM-based chunking, where input text is processed by an LLM to generate propositions. The input text consists of two sentences: "Alex visited the library." and "He loves reading.". The LLM processes this input, and the output propositions are the same two sentences, "Alex visited the library." and "Alex loves reading.". The diagram shows the transformation of the input text into propositions using an LLM.

**Key data points**
- Input text: Alex visited the library. He loves reading.
- Propositions: Alex visited the library. Alex loves reading.
[FIGURE_CAPTION END]

Each of the discussed techniques has its strengths, and the choice depends on the RAG system's specific requirements and the nature of the documents being processed. New approaches continue to emerge, such as late chunking, which processes text through long-context embedding models before splitting it into chunks to better preserve document-wide context.


--- Page 4 ---

## Pre-retrieval Optimization Techniques

Index optimization techniques enhance retrieval accuracy by structuring external data in more organized, searchable ways. These techniques can be applied to both data pre-processing and chunking stages in the RAG pipeline, ensuring that relevant information is effectively retrieved.

### Query Transformation

Using the user query directly as the search query for retrieval can lead to poor search results. That’s why turning the raw user query into an optimized search query is essential. Query transformation refines and expands unclear, complex, or ambiguous user queries to improve the quality of search results.

Query Rewriting involves reformulating the original user query to make it more suitable for retrieval. This is particularly useful in scenarios where user queries are not optimally phrased or expressed differently. This can be achieved by using an LLM to rephrase the original user query or employing specialized smaller language models trained specifically for this task.

This approach is called 'Rewrite-Retrieve-Read' instead of the traditional 'Retrieve-then-Read' paradigm.

[FIGURE_CAPTION START]
**High level description**
The image presents two flowcharts depicting query transformation techniques. The first flowchart illustrates Query Rewriting, starting with a 'Raw Query', processing it through a 'Query Re-writer (LLM)', resulting in a 'Rewritten Query', which is then passed to a 'Retriever' to obtain 'Retrieved Documents'. The second flowchart illustrates Query Expansion, starting with a 'Raw Query', processing it through a 'Query Re-writer (LLM)', resulting in multiple 'Expanded Queries', which are then passed to a 'Retriever' to obtain 'Retrieved Documents'.

**Key data points**
- Raw Query: Can you tell me which movies were popular last summer? I'm trying to find a blockbuster film.
- Rewritten Query: What were the top-grossing movies released last summer?
- Raw Query: What are the benefits of meditation?
- Expanded Queries: How does meditation reduce stress and anxiety?
- Expanded Queries: Can meditation improve focus and concentration?
- Expanded Queries: What are the long-term mental health benefits of meditation?
- Expanded Queries: How does meditation affect sleep quality?
[FIGURE_CAPTION END]

Query Expansion focuses on broadening the original query to capture more relevant information. This involves using an LLM to generate multiple similar queries based on the user's initial input. These expanded queries are then used in the retrieval process, increasing both the number and relevance of retrieved documents.

Note: Due to the increased quantity of retrieved documents, a reranking step is often necessary to prioritize the most relevant results (see Re-ranking).


--- Page 5 ---

### Query Decomposition

[FIGURE_CAPTION START]
**Figure title**
Query Decomposition

**High level description**
The diagram illustrates the Query Decomposition technique, which breaks down a complex input query into simpler sub-queries. The process involves two stages: Stage I, where the complex input query is decomposed into sub-queries using a Decomposition LLM, and Stage II, where a Retriever retrieves relevant documents based on the sub-queries. The sub-queries are labeled as "Sub-query 1", "Sub-query 2", and "Sub-query 3". Finally, an LLM synthesizes the retrieved information to generate a final response.

**Key data points**
- Sub-query 1
- Sub-query 2
- Sub-query 3
[FIGURE_CAPTION END]

Query decomposition is a technique that breaks down complex queries into simpler sub- queries. This is useful for answering multifaceted questions requiring diverse information sources, leading to more precise and relevant search results.

The process typically involves two main stages: decomposing the original query into smaller, focused sub-queries using an LLM and then processing these sub-queries to retrieve relevant information.

For example, the complex query “Why am I always so tired even though I eat healthy? Should I be doing something different with my diet or maybe try some diet trends?” can be decomposed into the following three simpler sub-queries:

1. What are the common dietary factors that can cause fatigue?
2. What are some popular diet trends and their effects on energy levels?
3. How can I determine if my diet is balanced and supports my energy needs?

Each sub-query targets a specific aspect, enabling the retriever to find relevant documents or chunks. Sub-queries can also be processed in parallel to improve efficiency. Additional techniques like keyword extraction and metadata filter extraction can help identify both key search terms and structured filtering criteria, enabling more precise searches. After retrieval, the system aggregates and synthesizes results from all sub-queries to generate a comprehensive answer to the original complex query.

### Query Routing

Query routing is a technique that directs queries to specific pipelines based on their content and intent, enabling a RAG system to handle diverse scenarios effectively. It works by analyzing each query and choosing the best retrieval method or processing pipeline to provide an accurate response. This often requires implementing multi-index strategies, where different types of information are organized into separate, specialized indexes optimized.

The process can include agentic elements, where AI agents decide how to handle each query. These agents evaluate factors such as query complexity and domain to determine the optimal approach. For example, fact-based questions may be routed to one pipeline, while those requiring summarization or interpretation are sent to another.

Agentic RAG functions like a network of specialized agents, each with different expertise. It can choose from various data stores, retrieval strategies (keyword-based, semantic, or hybrid), query transformations (for poorly structured queries), and specialized tools or APIs, such as text-to-SQL converters or even web search capabilities.

[FIGURE_CAPTION START]
**Figure title**
Single Agent RAG System (Router)

**High level description**
The figure illustrates a Single Agent RAG System (Router). The system starts with a "Query" which is then processed by a "Retrieval Agent". The Retrieval Agent uses "Tools" such as "Vector search engine A", "Vector search engine B", "Calculator", and "Web search" to retrieve information from "Collection A" and "Collection B". Finally, the retrieved information is processed by an "LLM" to generate a "Response".
[FIGURE_CAPTION END]


--- Page 6 ---

## Retrieval Optimization Strategies

Retrieval optimization strategies aim to improve retrieval results by directly manipulating the way in which external data is retrieved in relation to the user query. This can involve refining the search query, such as using metadata to filter candidates or excluding outliers, or even involve fine-tuning an embedding model on external data to improve the quality of the underlying embeddings themselves.

[FIGURE_CAPTION START]
**Figure title**
Metadata Filtering

**High level description**
The flowchart illustrates metadata filtering, starting with a query and a vector database. The process filters vectors based on user metadata, specifically filtering out vectors where the user is not "Alice". The diagram shows the initial vectors for users Alice, Bob, and John, and then demonstrates how the filtering stage removes Bob and John, resulting in only Alice's vector being passed to the vector search and ultimately to the results.

**Key data points**
- User = "Alice", Vector = [2.5, 2.5]
- User = "Bob", Vector = [2.0, 2.0]
- User = "John", Vector = [3.0, 3.0]
[FIGURE_CAPTION END]

### Metadata Filtering

Metadata is the additional information attached to each document or chunk in a vector database, providing valuable context to enhance retrieval. This supplementary data can include timestamps, categories, author info, source references, languages, file types, etc.

When retrieving content from a vector database, metadata helps refine results by filtering out irrelevant objects, even when they are semantically similar to the query. This narrows the search scope and improves the relevance of the retrieved information.

Another benefit of using metadata is time-awareness. By incorporating timestamps as metadata, the system can prioritize recent information, ensuring the retrieved knowledge remains current and relevant. This is particularly useful in domains where information freshness is critical.

To get the most out of metadata filtering, it's important to plan carefully and choose metadata that improves search without adding unnecessary complexity.


--- Page 7 ---

### Excluding Vector Search Outliers

The most straightforward approach to defining the number of returned results is explicitly setting a value for the top k (top_k) results. If you set top_k to 5, you'll get the five closest vectors, regardless of their relevance. While easy to implement, this can include poor matches just because they made the cutoff.

Here are two techniques to manage the number of search results implicitly that can help with excluding outliers:

[FIGURE_CAPTION START]
**High level description**
The diagram illustrates distance thresholding, where data points are represented as circles. Some circles are filled with a light blue color, while others are white. A dashed circle represents the distance threshold. The light blue circles inside the dashed circle are considered within the threshold, while the white circles outside are considered outliers.
[FIGURE_CAPTION END]

[FIGURE_CAPTION START]
**High level description**
The diagram shows a target-like pattern with concentric dashed circles. There are several white circles and a few light blue circles scattered around the diagram. The light blue circles are clustered near the center of the concentric circles, while the white circles are located further away from the center.
[FIGURE_CAPTION END]

Distance thresholding adds a quality check by setting a maximum allowed distance between vectors. Any result with a distance score above this threshold gets filtered out, even if it would have made the top_k cutoff. This helps remove the obvious bad matches but requires careful threshold adjustment.

Autocut is more dynamic - it looks at how the result distances are clustered. Instead of using fixed limits, it groups results based on their relative distances from your query vector. When there's a big jump in distance scores between groups, Autocut can cut off the results at that jump. This catches outliers that might slip through top_k or basic distance thresholds.

[FIGURE_CAPTION START]
**High level description**
The figure is a scatter plot showing the distribution of data points. Three data points are labeled as 1, 2, and 3, and are colored in light green. There are also three unlabeled data points shown as empty circles. The figure illustrates the concept of vector search outliers.

**Key data points**
- Data point 1
- Data point 2
- Data point 3
[FIGURE_CAPTION END]

### Hybrid Search

[FIGURE_CAPTION START]
**High level description**
The flowchart depicts a search process that starts with a "Query" which is then processed by both "Vector Search" and "Keyword Search". The "Vector Search" leads to "Context A", "Context B", and "Context C", while the "Keyword Search" leads to "Context B", "Context C", and "Context A". Both sets of contexts are then fed into a "Fusion Algorithm", which outputs "Context B", "Context A", and "Context C". The diagram illustrates how different search methods contribute to generating context, which is then combined by a fusion algorithm.
[FIGURE_CAPTION END]

Hybrid search combines the strengths of vector-based semantic search with traditional keyword-based methods. This technique aims to improve the relevance and accuracy of retrieved information in RAG systems.

The key to hybrid search lies in the 'alpha' (α) parameter, which controls the balance between semantic and keyword-based search methods:

- α = 1: Pure semantic search
- α = 0: Pure keyword-based search
- 0 < α < 1: Weighted combination of both methods

This approach is particularly beneficial when you need both contextual understanding and exact keyword matching.

Consider a technical support knowledge base for a software company. A user might submit a query like "Excel formula not calculating correctly after update". In this scenario, semantic search helps understand the context of the problem, potentially retrieving articles about formula errors, calculation issues, or software update impacts. Meanwhile, keyword search ensures that documents containing specific terms like "Excel" and "formula" are not overlooked.

Therefore, while implementing hybrid search, it’s crucial to adjust the alpha parameter based on your specific use case to optimize the performance.


--- Page 8 ---

### Embedding Model Fine-Tuning

Off-the-shelf embedding models are usually trained on large general datasets to embed a wide range of data inputs. However, embedding models can fail to capture the context and nuances of smaller, domain-specific datasets.

Fine-tuning embedding models on custom datasets can significantly improve the quality of embeddings, subsequently improving performance on downstream tasks like RAG. Fine-tuning improves embeddings to better capture the dataset's meaning and context, leading to more accurate and relevant retrievals in RAG applications.

The more niche your dataset is, the more it can benefit from embedding model fine-tuning. Datasets with specialized vocabularies, like medical or legal datasets, are ideal for embedding model fine-tuning, which helps extend out-of-domain vocabularies and enhance the accuracy and relevance of information retrieval and generation in RAG pipelines.

[FIGURE_CAPTION START]
**High level description**
This scatter plot visualizes customer reviews. The x and y axes are not explicitly labeled, but the position of each review suggests a relative rating of quality and overall satisfaction. Green data points represent positive reviews such as "Quality is amazing! Will definitely buy again!", "Love the design, but it broke in one week.", and "The movie was fun, but I wouldn't see it again.". Purple data points represent negative reviews such as "Food was decent, but service was terrible" and "Horrible quality. Lasted two days."
[FIGURE_CAPTION END]

To fine-tune an existing embedding model you first need to select a base model that you would like to improve. Next, you begin the fine-tuning process by providing the model with your domain-specific data. During this process, the loss function adjusts the model’s embeddings so that semantically similar items are placed closer together in the embedding space. To evaluate a fine-tuned embedding model, you can use a validation set of curated query-answer pairs to assess the quality of retrieval in your RAG pipeline. Now, the model is ready to generate more accurate and representative embeddings for your specific dataset.

[FIGURE_CAPTION START]
**High level description**
This is a scatter plot showing customer feedback. The x and y axes are not labeled. Each data point represents a different product or service, with associated qualitative feedback. The data points are color-coded: green for "Quality is amazing! Will definitely buy again!", light blue for "Love the design, but it broke in one week.", light blue for "The movie was fun, but I wouldn't see it again", light blue for "Food was decent, but service was terrible.", and purple for "Horrible quality. Lasted two days."
[FIGURE_CAPTION END]


--- Page 9 ---

[FIGURE_CAPTION START]
**High level description**
The flowchart illustrates a basic retrieval process. It starts with "Documents" and "Chunks", then a "Query" is processed by an "Embedding Model" and stored in a "Vector Database". The "Context" is retrieved, passed to a "Prompt Template", and finally processed by an "LLM" to generate a "Response". The flowchart uses arrows to indicate the flow of information between the different components.
[FIGURE_CAPTION END]

## Post-Retrieval Optimization Techniques

Post-retrieval optimization techniques aim to enhance the quality of generated responses, meaning that their work begins after the retrieval process has been completed. This diverse group of techniques includes using models to re-rank retrieved results, enhancing or compressing the retrieved context, prompt engineering, and fine-tuning the generative LLM on external data.

### Re-Ranking

One proven method to improve the performance of your information retrieval system is to leverage a retrieve-and-rerank pipeline. A retrieve-and-rerank pipeline combines the speed of vector search with the contextual richness of a re-ranking model.

In vector search, the query and documents are processed separately. First, the documents are pre-indexed. Then, at query time, the query is processed, and the documents closest in vector space are retrieved. While vector search is a fast method to retrieve candidates, it can miss contextual nuances.

This is where re-ranking models come into play. Because re-ranking models process the query and the documents together at query time, they can capture more contextual nuances. However, they are usually complex and resource-intensive and thus not suitable for first-stage retrieval like vector search.

By combining vector search with re-ranking models, you can quickly cast a wide net of potential candidates and then re-order them to improve the quality of relevant context in your prompt.

Note that when using a re-ranking model, you should over-retrieve chunks to filter out less relevant ones later.

[FIGURE_CAPTION START]
**Figure title**
Re-Ranking

**High level description**
The flowchart illustrates the re-ranking process, starting with a 'Query' and progressing through an 'Embedding Model' and 'Vector Database'. The 'Retrieved Context' is then re-ranked using a 'Reranker Model' to produce a 'Re-ranked Context'. This context is fed into a 'Prompt Template', and finally, an 'LLM' generates a 'Response'. The re-ranking portion of the flow is highlighted in green.
[FIGURE_CAPTION END]


--- Page 10 ---

### Context Post-Processing

After retrieval, it can be beneficial to post-process the retrieved context for generation. For example, if the retrieved context might benefit from additional information you can enhance it with metadata. On the other hand, if it contains redundant data, you can compress it.

#### Context Enhancement with Metadata

One post-processing technique is to use metadata to enhance the retrieved context with additional information to improve generation accuracy. While you can simply add additional information from the metadata, such as timestamps, document names, etc., you can also apply more creative techniques.

Context enhancement is particularly useful when data needs to be pre-processed into smaller chunk sizes to achieve better retrieval precision that doesn’t contain enough contextual information to generate high-quality responses. In this case, you can apply a technique called “Sentence window retrieval”. This technique chunks the initial document into smaller pieces (usually single sentences) but stores a larger context window in its metadata. At retrieval time, the smaller chunks help improve retrieval precision. After retrieval, the retrieved smaller chunks are replaced with the larger context window to improve generation quality.

[FIGURE_CAPTION START]
**High level description**
The diagram illustrates a process where a 'Sentence embedding' is connected to a 'Window (n sentences before and after sentence)', which in turn is connected to an 'LLM'. This process is shown twice, with a slight variation in the background color. The diagram appears to represent a system or method for processing sentences using a language model, potentially for tasks like contextual understanding or text generation.
[FIGURE_CAPTION END]

#### Context Compression

RAG systems rely on diverse knowledge sources to retrieve relevant information. However, this often results in the retrieval of irrelevant or redundant data, which can lead to suboptimal responses and costly LLM calls (more tokens).

Context compression effectively addresses this challenge by extracting only the most meaningful information from the retrieved data. This process begins with a base retriever that retrieves documents/chunks related to the query. These documents/chunks are then passed through a document compressor that shortens them and eliminates irrelevant content, ensuring that valuable data is not lost in a sea of extraneous information.

Contextual compression reduces data volume, lowering retrieval and operational costs. Current research focuses on two main approaches: embedding-based and lexical-based compression, both of which aim to retain essential information while easing computational demands on RAG systems.

[FIGURE_CAPTION START]
**High level description**
The flowchart depicts the context compression process in a RAG system. It starts with a "Query" that is passed to an "Embedding Model" and then to a "Vector Database". The "Context" is then processed by a "Compressor" to produce a "Compressed Context". Finally, a "Prompt Template" uses the compressed context, and the output is sent to an "LLM" to generate a "Response". The "Context Compression" block is highlighted in light green.
[FIGURE_CAPTION END]


--- Page 11 ---

### Prompt Engineering

The generated outputs of LLMs are greatly influenced by the quality, tone, length, and structure of their  corresponding prompts. Prompt engineering is the practice of optimizing LLM prompts to improve the quality and  accuracy of generated output. Often one of the lowest-hanging fruits when it comes to techniques for improving RAG  systems, prompt engineering does not require making changes to the underlying LLM itself. This makes it an efficient  and accessible way to enhance performance without complex modifications.

There are several different prompting techniques that are especially useful in improving RAG pipelines.

[FIGURE_CAPTION START]
**High level description**
The figure is a flowchart depicting the Chain of Thought (CoT) prompting technique. The process starts with a "Prompt", which leads to a series of "Thought" steps, represented by two "Thought" boxes with an ellipsis in between. Finally, the process concludes with a "Response". The arrows indicate the flow of the process from top to bottom.
[FIGURE_CAPTION END]

Chain of Thought (CoT) prompting involves asking  the model to “think step-by-step” and break down  complex reasoning tasks into a series of  intermediate steps. This can be especially useful  when retrieved documents contain conflicting or  dense information that requires careful analysis.

[FIGURE_CAPTION START]
**High level description**
This is a flowchart illustrating a process that starts with a 'Prompt' and leads to a 'Response'. The process involves multiple 'Thought' steps, arranged in a hierarchical structure. The 'Thought' nodes are color-coded, with some being green and others being red or pink, potentially indicating different categories or types of thoughts. The arrows indicate the flow of the process from the initial prompt through various thought processes to the final response.
[FIGURE_CAPTION END]

Tree of Thoughts (ToT) prompting builds on CoT by  instructing the model to evaluate its responses at each step  in the problem-solving process or even generate several  different solutions to a problem and choose the best result.  This is useful in RAG when there are many potential pieces of  evidence, and the model needs to weigh different possible  answers based on multiple retrieved documents.

[FIGURE_CAPTION START]
**High level description**
This diagram illustrates a cyclical process. It starts with a "Prompt" which leads to a "Thought". The "Thought" then leads to an "Action" which affects the "Environment". The "Environment" then leads to an "Observation" which affects the "Thought". The "Thought" also leads to a "Response".
[FIGURE_CAPTION END]

ReAct (Reasoning and Acting) prompting combines CoT with  agents, creating a system in which the model can generate  thoughts and delegate actions to agents that interact with  external data sources in an iterative process. ReAct can improve  RAG pipelines by enabling LLMs to dynamically interact with  retrieved documents, updating reasoning and actions based on  external knowledge to provide more accurate and contextually  relevant responses.


--- Page 12 ---

### LLM Fine-Tuning

RAG Pipeline

[FIGURE_CAPTION START]
**Figure title**
LLM Fine-Tuning

**High level description**
The diagram illustrates the LLM Fine-Tuning process within a RAG pipeline. The RAG pipeline includes components such as Documents, Chunks, Query, Response, Embedding Model, Vector Database, Context, Prompt Template, and LLM. The diagram shows the flow of data from the initial query to the final response, highlighting the role of pre-trained LLMs and fine-tuned LLMs in the process. The LLM Fine-tuning box shows the transition from a pre-trained LLM to a fine-tuned LLM using a domain-specific dataset.
[FIGURE_CAPTION END]

Pre-trained LLMs are trained on large, diverse datasets to acquire a sense of general knowledge, including language and grammar patterns, extensive vocabularies, and the ability to perform general tasks. When it comes to RAG, using pre-trained LLMs can sometimes result in generated output that is too generic, factually incorrect, or fails to directly address the retrieved context.

Fine-tuning a pre-trained model involves training it further on a specific dataset or task to adapt the model's general knowledge to the nuances of that particular domain, improving its performance in that area. Using a fine-tuned model in RAG pipelines can help improve the quality of generated responses, especially when the topic at hand is highly specialized.

High-quality domain-specific data is crucial for fine-tuning LLMs. Labeled datasets, like positive and negative customer reviews, can help fine-tuned models better perform downstream tasks like text classification or sentiment analysis. Unlabeled datasets, on the other hand, like the latest articles published on PubMed, can help fine-tuned models gain more domain-specific knowledge and expand their vocabularies.

During the fine-tuning process, the model weights of the pre-trained LLM (also referred to as a base model) are iteratively updated through a process called backpropagation to learn from the domain-specific dataset. The result is a fine-tuned LLM that better captures the nuances and requirements of the new data, such as specific terminology, style, or tone.

## Summary

RAG enhances generative models by enabling them to reference external data, improving response accuracy and relevance while mitigating hallucinations and information gaps. Naive RAG retrieves documents based on query similarity and directly feeds them into a generative model for response generation. However, more advanced techniques, like the ones detailed in this guide, can significantly improve the quality of RAG pipelines by enhancing the relevance and accuracy of the retrieved information.

This e-book reviewed advanced RAG techniques that can be applied at various stages of the RAG pipeline to improve retrieval quality and accuracy of generated responses.

- Indexing optimization techniques, like data preprocessing and chunking focus on formatting external data to improve its efficiency and searchability.
- Pre-retrieval techniques aim to optimizing the user query itself by rewriting, reformatting, or routing queries to specialized pipelines
- Retrieval optimization strategies often focus on refining search results during the retrieval phase.
- Post-retrieval optimization strategies aim to improve the accuracy of generated results through a variety of techniques including, re-ranking retrieved results, enhancing or compressing the (retrieved) context, and manipulating the prompt or generative model (LLM).

We recommend implementing a validation pipeline to identify which parts of your RAG system need optimization and to assess the effectiveness of advanced techniques. Evaluating your RAG pipeline enables continuous monitoring and refinement, ensuring that optimizations positively impact retrieval quality and model performance.

## Ready to supercharge your
RAG applications?

Start building today with a 14 day free
trial of Weaviate Cloud (WCD).

Try Now

[FIGURE_CAPTION START]
**High level description**
The diagram shows a screen with code, which is connected to a hexagon shape with a logo inside. The hexagon is connected to a square divided into four smaller squares, each containing a different icon. The diagram illustrates a process or workflow, possibly related to software development or data processing.
[FIGURE_CAPTION END]

Contact Us