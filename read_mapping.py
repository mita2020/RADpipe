#!/usr/bin/env python

##print __name__

import optparse
import os

usage_line = """
read_mapping.py

Version 1.0 (8 September, 2014)
License: GNU GPLv2
To report bugs or errors, please contact Daren Card (dcard@uta.edu).
This script is provided as-is, with no support and no guarantee of proper or desirable functioning.

Script that takes read files (paired or unpaired) and maps them to a reference sequence (genome) using bwa.
Note that this script only uses the 'mem' bwa mapping algorithm and can't be used with other algorithms without
modification. Input is a reference sequence in fasta format and the directory containing the read files to be
mapped (without beginning or ending /). Naming conventions for read files are as follows:
1. The file extension (normally fastq) must match that passed to the command with the '--ext' flag.
2. Prior to the extension, there must be an indication of the read type (single or paired) as follows:
	a. P1 and P2 for paired reads, with P1 designated for the single-end reads and P2 designated for the paired-end reads
	b. S1 and S2 for paired reads in which the pairs were broken during quality trimming, with S1 designated
	for the single-end broken reads and S2 designated for the paired-end broken reads.
	c. S1 for non-paired, single-end reads
3. A file root with the name of the sample
Example: ID1234_Loc1_ACTTAG-GTACAG.P1.fastq = single-end reads of paired reads of sample ID1234_Loc1_ACTTAG-GTACAG
Note: Reads that do not have this file name formatting will probably not be run correctly.

Either a '-p' flag for paired reads or a '-s' flag for single-end reads only needs to be passed to the program.
One can also pass the number of threads that can be used for mapping and any of the bwa mapping flags (as one text string).
The script will create an indexed reference, map all reads from each sample to the reference to create a SAM mapping file,
convert the SAM mapping file to a BAM mapping file, merge BAM mapping files where necessary, and sort and index each sample
BAM file. It will also remove the larger SAM files to save on space unless the '--keep_sams' flag is passed. All mapping
files are outputted to the 'mapping' directory that is created in the working directory by the script.

python read_mapping.py -p/-s --reference <reference.fasta> --read_dir <directory_of_reads> --ext <file_ext> [--threads <#threads>
--bwa_opts "<options_string>" --keep_sams --no_index]							
"""

#################################################
###           Parse command options           ###
#################################################

usage = usage_line
                        
parser = optparse.OptionParser(usage=usage)
parser.add_option("--reference", action = "store", type = "string", dest = "reference", help = "the reference genome you will be mapping to")
parser.add_option("--read_dir", action = "store", type = "string", dest = "directory", help = "the directory containing your reads")
parser.add_option("--threads", action = "store", type = "string", dest = "threads", help = "number of threads/cores to use [1]", default = "1")
parser.add_option("--ext", action = "store", dest = "ext", help = "the file extension of the read files")
parser.add_option("--bwa_opts", action = "store", dest = "bwa", help = "all additional bwa mapping options as a text string, in quotes")
parser.add_option("--keep_sams", action = "store_true", dest = "sams", help = "keep the SAM mapping files", default = "False")
parser.add_option("--no_index", action = "store_true", dest = "index", help = "pass flag to turn off reference indexing (i.e., if already complete)")
parser.add_option("-p", action = "store_true", dest = "paired", help = "paired-end reads")
parser.add_option("-s", action = "store_true", dest = "single", help = "single-end reads only")

options, args = parser.parse_args()


#################################################
###         Setup mapping enviornment         ###
#################################################

def setup():
	os.system("mkdir mapping")											# make 'mapping' directory (may error if already present)
	if options.index is True:											# If reference is already indexed, can skip lengthy indexing
		print "\n***Not indexing reference genome***\n"					# by passing '--no_index' flag
	else:									
		print "\n***Indexing reference genome***\n"
		os.system("bwa index "+options.reference)						# Otherwise $ bwa index <reference>


#################################################
###        Create single-end dictionary       ###
#################################################

def make_SE_dict(name):													
	SE_dict = {}
#	print "\n***Making SE_dict***\n"
	root = name
	ext = options.ext
	nameS1 = str(root)+".S1."+str(ext)									# Set S1 to sample.S1.ext
	nameS2 = str(root)+".S2."+str(ext)									# Set S2 to sample.S2.ext
	nameBroken = str(root)+".broken."+str(ext)
	if nameS1 not in SE_dict.keys():									# If S1 not in dictionary, add it and S2
		SE_dict[nameS1] = [nameS2, nameBroken]
	cat_SE(SE_dict)														# Concatenate S1 and S2 read files
#	print SE_dict
	return SE_dict														# Return SE_dict for future use


#################################################
###        Concatenate single-end reads       ###
#################################################
	
def cat_SE(SE_dict):
	print "\n***Concatenating broken pairs (ignore errors)***\n"
	for key in SE_dict.keys():											# For each S1 key in SE_dict
		foo = key.split(".")											# split by '.'
		file = foo[0]+".SE."+options.ext								# output file = sample.SE.ext
		value = SE_dict[key]											# look up S2 value
# command = $ cat sample.S1.ext sample.S2.ext sample.broken.ext > sample.SE.ext (may error if no S2 or broken)
		print "cat ./"+options.directory+"/"+key+" ./"+options.directory+"/"+value[0]+" ./+options.directory+"/"+value[1]+" > ./"+options.directory+"/"+file
		os.system("cat ./"+options.directory+"/"+key+" ./"+options.directory+"/"+value[0]+" ./+options.directory+"/"+value[1]+" > ./"+options.directory+"/"+file)


#################################################
###           Map single-end reads            ###
#################################################

def SE_map(name):	
	SE_dict = make_SE_dict(name)										# Run 'make_SE_dict' and pass name, return SE_dict
	for key in SE_dict.keys():											# for each SE_dict key
		foo = key.split(".")											# split by '.'
		print "\n***Mapping single-end reads from "+foo[0]+"***\n"
		input = foo[0]+".SE."+options.ext								# input SE file for mapping
		file = foo[0]+".SE.sam"											# output SE file from mapping (.sam)
		if options.bwa == None:											# If no additional bwa options passed
			params = ""
		else:															# If additional bwa options passed
			params = options.bwa
# command = $ bwa mem -t <input_threads> <other_bwa_opts> <reference> <SE_input> > ./mapping/<SAM_output> !! output put into 'mapping'
		print "bwa mem -t "+str(options.threads)+" "+str(params)+" ./"+options.reference+" ./"+options.directory+"/"+input+" > ./mapping/"+file
		os.system("bwa mem -t "+str(options.threads)+" "+str(params)+" ./"+options.reference+" ./"+options.directory+"/"+input+" > ./mapping/"+file)
		sam2bam(file)													# Run sam2bam


#################################################
###        Create paired-end dictionary       ###
#################################################

def make_PE_dict(name):
	PE_dict = {}
	root = name															# sample name is root
	ext = options.ext													# user-specified extension
	nameP1 = str(root)+".P1."+str(ext)									# name of P1 read
	nameP2 = str(root)+".P2."+str(ext)									# name of P2 read
	if nameP1 not in PE_dict.keys():									# if P1 read not in dictionary
		PE_dict[nameP1] = nameP2										# add P1 as key and P2 as value
#	print PE_dict
	return PE_dict														# Return PE_dict for future use


#################################################
###           Map paired-end reads            ###
#################################################

def PE_map(name):											
	PE_dict = make_PE_dict(name)										# Run 'make_PE_dict' and pass name, return PE_dict
	for key in PE_dict.keys():											# For each set of paired reads
		foo = key.split(".")											# Split file name by '.'
		print "\n***Mapping paired-end reads from "+foo[0]+"***\n"
		file = foo[0]+".PE.sam"											# Make output file name
		value = PE_dict[key]											# Look up P2 reads name
		if options.bwa == None:											# If no additional bwa options passed
			params = ""
		else:															# If additional bwa options passed
			params = options.bwa
# command = $ bwa mem -t <input_threads> <other_bwa_opts> <reference> <P1_input> <P2_input> > ./mapping/<SAM_output> !! output put into 'mapping'
		print "bwa mem -t "+str(options.threads)+" "+str(params)+" ./"+options.reference+" ./"+options.directory+"/"+key+" ./"+options.directory+"/"+value+" > ./mapping/"+file
		os.system("bwa mem -t "+str(options.threads)+" "+str(params)+" ./"+options.reference+" ./"+options.directory+"/"+key+" ./"+options.directory+"/"+value+" > ./mapping/"+file)
		sam2bam(file)													# run sam2bam


#################################################
###             Convert SAM to BAM            ###
#################################################

def sam2bam(file):
	name = file.split(os.extsep)										# Split .sam file into parts
	print "\n***Converting SAM to BAM***\n"
	input = name[0]+"."+name[1]+".sam"									# Put together input .sam file name
	output = name[0]+"."+name[1]+".bam"									# Put together output .bam file name
# command = $ samtools view -bS ./mapping/<input_sam> > ./mapping/<output_bam> !! Working in 'mapping'
	print "samtools view -bS ./mapping/"+input+" > ./mapping/"+output
	os.system("samtools view -bS ./mapping/"+input+" > ./mapping/"+output)


#################################################
###      Process paired-end mapping files     ###
#################################################
	
def PE_bam_process(name):
	PEin = name+".PE.bam"												# Input PE bam
	SEin = name+".SE.bam"												# Input SE bam
	Merge_out = name+".merge.bam"										# name for merged (PE+SE) bam output file
	Sort_out = name+".merge.sort"										# name for sorted, merged bam output file
## MERGE
	print "\n***Merging single-end and paired-end BAMs together***\n"
# command = $ samtools merge -f ./mapping/<merged_bam> ./mapping/<PE_bam> ./mapping/<SE_bam> !! force overwrite
	print "samtools merge -f ./mapping/"+Merge_out+" ./mapping/"+PEin+" ./mapping/"+SEin
	os.system("samtools merge -f ./mapping/"+Merge_out+" ./mapping/"+PEin+" ./mapping/"+SEin)
## SORT
	print "\n***Sorting BAM***\n"
# command = $ samtools sort ./mapping/<merged_bam> ./mapping/<sort_prefix>
	print "samtools sort ./mapping/"+Merge_out+" ./mapping/"+Sort_out
	os.system("samtools sort ./mapping/"+Merge_out+" ./mapping/"+Sort_out)
## INDEX MAPPING
	print "\n***Indexing BAM***\n"
# command = $ samtools index ./mapping/<sort_prefix>.bam
	print "samtools index ./mapping/"+Sort_out+".bam"
	os.system("samtools index ./mapping/"+Sort_out+".bam")
## GENERATE MAPPING REPORT
	print "\n***Generating mapping summary report***\n"
# command = $ samtools flagstat ./mapping/<sort_prefix>.bam > ./mapping/<sort_prefix>.bam.report
	print "samtools flagstat ./mapping/"+Sort_out+".bam > ./mapping/"+Sort_out+".bam.report"
	os.system("samtools flagstat ./mapping/"+Sort_out+".bam > ./mapping/"+Sort_out+".bam.report")
## CONVERT SORTED BAM BACK TO SAM
	print "\n***Converting the sorted BAM back to a final SAM***\n"
# command = $ samtools view -h ./mapping/<sort_prefix>.bam > ./mapping/<sort_prefix>.sam
	print "samtools view -h ./mapping/"+Sort_out+".bam > ./mapping/"+Sort_out+".sam"
	os.system("samtools view -h ./mapping/"+Sort_out+".bam > ./mapping/"+Sort_out+".sam")


#################################################
###      Process single-end mapping files     ###
#################################################

def SE_bam_process(name):
	SEin = name+".SE.bam"												# Input SE bam
	Sort_out = name+".sort"												# name for sorted SE bam output file
## SORT
	print "\n***Sorting BAM***\n"
# command = $ samtools sort ./mapping/<SE_bam> ./mapping/<sort_prefix>
	print "samtools sort ./mapping/"+SEin+" ./mapping/"+Sort_out
	os.system("samtools sort ./mapping/"+SEin+" ./mapping/"+Sort_out)
## INDEX MAPPING
	print "\n***Indexing BAM***\n"
# command = $ samtools index ./mapping/<sort_prefix>.bam
	print "samtools index ./mapping/"+Sort_out+".bam"
	os.system("samtools index ./mapping/"+Sort_out+".bam")
## GENERATE MAPPING REPORT
	print "\n***Generating mapping summary report***\n"
# command = $ samtools flagstat ./mapping/<sort_prefix>.bam > ./mapping/<sort_prefix>.bam.report
	print "samtools flagstat ./mapping/"+Sort_out+".bam > ./mapping/"+Sort_out+".bam.report"
	os.system("samtools flagstat ./mapping/"+Sort_out+".bam > ./mapping/"+Sort_out+".bam.report")
## CONVERT SORTED BAM BACK TO SAM
	print "\n***Converting the sorted BAM back to a final SAM***\n"
# command = $ samtools view -h ./mapping/<sort_prefix>.bam > ./mapping/<sort_prefix>.sam
	print "samtools view -h ./mapping/"+Sort_out+".bam > ./mapping/"+Sort_out+".sam"
	os.system("samtools view -h ./mapping/"+Sort_out+".bam > ./mapping/"+Sort_out+".sam")

#################################################
###       Remove intermediate SAM output      ###
#################################################
	
def remove_sams():
	if options.sams == True:										# If user elects to keep all SAMs
		print "\n***As specified, SAM output will be saved!***\n"
	else:															# Else, if no election to keep SAMs, delete anything with *.sam
		print "\n***Removing unnecessary intermediate SAM output!***\n"
		os.system("rm -f ./mapping/*.sam")


#################################################
###            	   Full Program               ###
#################################################
		
def main():
	if options.reference is None:									# User didn't input reference genome
		print "\n***Error: specify reference for mapping!***\n"
	if options.directory is None:									# User didn't input directory containing read files
		print "\n***Error: specify directory containing read files!***\n"
	if options.ext is None:											# User didn't specify read file extension (e.g., fastq)
		print "\n***Error: specify the file extension for the read files!***\n"
	else:
		setup()														# Setup the pipeline environment
		print "\n***Running mapping pipeline***\n"
		for root,dirs,files in os.walk(options.directory):			# Gather all objects in specified directory
			print "\n***Gathing read files from specified directory***\n"
		names = {}
		for file in files:
			if file.endswith("."+options.ext):						# If file ends with specified extension
				foo = file.split(os.extsep)
				name = foo[0]										# Take root of file name (everything up to 1st period)
				if name not in names.keys():
					names[name] = 1									# Store each unique file root in dictionary
#		print names
		for name in names.keys():									# For each unique file name in dictionary
			if options.single == True:								# If user specifies reads as single-end only
				SE_map(name)										# Run single-end mapping pipeline
				SE_bam_process(name)
				remove_sams()
				print "\n***Mapping complete! See 'mapping' directory for results!***\n"
			elif options.paired == True:							# If user specifies reads as paired-end
				PE_map(name)										# Run paired-end mapping pipeline
				SE_map(name)
				PE_bam_process(name)
				remove_sams()
				print "\n***Mapping complete for "+name+"! See 'mapping' directory for results!***\n"
			else:													# If user doesn't specified single or paired, error
				print "\n***Error: specify whether reads are single-end only ('-s') or paired end ('-p')!***\n"


#################################################
###              Run Full Program             ###
#################################################
		
main()
