import os
import re

import gzip
import time
from operator import itemgetter

class Remove_Classes():
    
    ######### INIT #########
    def __init__(self, temp):
        '''temp - should be the path to temp folder'''
        self.temp = temp
        self.classes_to_remove = set()
        self.classes_to_protect = set()
        
    def count_classes(self, isa, p279star, claims):
        '''Finds all classes from isa and p279star files, then counts instances of classes in claims file'''
        #Get union of classes from isa and p279star files
        self.class_set = self.find_all_classes(isa, p279star)

        #Query the claims file, and get a count of each class
        self.class_counts = self.get_class_counts(claims)
    
    def find_all_classes(self, isa, p279star): #called by count_classes()
        isa_p = isa.replace('\\', '')
        p279star_p = p279star.replace('\\', '')
        class_files = [isa_p, p279star_p]
        class_set = set()
        for file in class_files:
            fd = gzip.open(file, 'rt')
            lines=fd.readlines()
            count = 0
            for line in lines[1:]:
                qnode = line.split('\t')[2].strip()
                class_set.add(qnode)
        return class_set
    
    def get_class_counts(self, claims): #called by count_classes()
        claims_p = claims.replace('\\', '')
        fd = gzip.open(claims_p, 'rt')
        lines=fd.readlines()

        class_counts = dict()
        for line in lines[1:]:
            n1 = line.split('\t')[1]
            n2 = line.split('\t')[3]
            for n in [n1, n2]:
                if n in self.class_set:
                    if n not in class_counts: class_counts[n] = 1
                    else: class_counts[n] += 1
        return class_counts
    
    ######### METHODS #########                       
    def add_instances(self, instances, **kwargs):
        '''Identify the set of all classes for a list of instances
        instancess - a list of Wikidata instances <list> 
        kwargs: remove - whether to add to the remove_list or protect_list (True/False)'''
        if kwargs:
            for qnode in instances:
                # !wd u {qnode} > {self.temp}/summary.txt #ipynb
                command = f"wd u {qnode} > {self.temp}/summary.txt" #py
                os.system(command)
                fd = open(f'{self.temp}/summary.txt', "r")
                lines = fd.readlines()
                for line in lines:
                    if line.split(":")[0] in ['instance of (P31)', 'subclass of (P279)']:
                        classes_raw = line.split(":")[1].split('|')
                        for c in classes_raw:
                            res = re.findall(r'\(.*?\)', c)[0].replace('(','').replace(')','')

                            #Add to remove_list or protect_list based on `remove` setting
                            if kwargs['remove']: 
                                self.classes_to_remove.add(res)
                            else:
                                print('result: ', res)
                                self.add_classes_to_protect([res])
        else: print('Error: Please specify remove parameter; ex: remove=False, remove=True')
        
    def add_classes_to_remove(self, **kwargs):
        '''Add classes manually to set of classes to remove
        kwargs: classes - a list of Wikidata classes <list>
        kwargs: size - adds classes with # instances < size'''
        if 'classes' in kwargs:
            if isinstance(kwargs['classes'], list):
                [self.classes_to_remove.add(c) for c in kwargs['classes']]
            else: 
                print('must pass in a list of classes')
        if 'size' in kwargs:
            for key in self.class_counts.keys():
                if self.class_counts[key] <= kwargs['size']: 
                    self.classes_to_remove.add(key)

    def add_classes_to_protect(self, classes):
        '''Add classes manually to set of classes to protect
        args: classes - list of Wikidata classes'''
        for c in list(classes):
            # !wdtaxonomy -r {c} -f csv -o {self.temp}/superclass_raw.txt #ipynb
            command = f'wdtaxonomy -r {c} -f csv -o {self.temp}/superclass_raw.txt' #py
            os.system(command)
            fd = open(f'{self.temp}/superclass_raw.txt', "r")
            lines = fd.readlines()
            for line in lines[1:]:
                qnode = line.split(',')[1]
                if qnode[0].lower() == 'q': 
                    self.classes_to_protect.add(qnode)