Problem to be solved.

A unified digital forensics investigation app created to solve the following problems
- easy to use without training and supports quick creating of case 
-  doesn't store but quickly ingest files via hashing of collected files for later investigation 
- users data will be hashed and encrypted
- creating a storyline that is convincing for even non technical persons
- integrity of evidence files


## 1 Easy to use without training and supports quick creating of case 



   1. This problem will be solved by creating an easy to use interface
   2. Consisting of A quick create and add evidence button
   3. A View Case button
   
> For now we're building the cli version so this ideas will be implemented in the CLI 

Things to start working on to solve this problem 

- create the cli interface done
- create the cli version of the case creation done
- cli view case and chain of custody works done
- Export case as JSON (full ledger export – very useful for the “offline-first + sync later” goal) done
- Generate a simple text/Markdown report for a case
- Delete / close a case (with custody logging) done
- Search evidence by hash 
- Better input validation + error messages
- Add a progress bar when hashing large files (the E01 was 300 MB) done
