#!/usr/bin/env python

##print __name__

import re
import sys
import os
import optparse
import subprocess

usage_line = """
process_rawreads.py

Version 2.0 (2 December, 2014)
License: GNU GPLv2
To report bugs or errors, please contact Daren Card (dcard@uta.edu).
This script is provided as-is, with no support and no guarantee of proper or desirable functioning.

Script that process raw RADseq reads that are generated using the Peterson et al. 2012 ddRADseq \
protocol. The script filters out PCR clones, trims away the 8bp unique molecular identifiers at \
the beginning of each read, parses by combinatorial barcodes (an inline barcode and standard Illumina \
index), and quality trims using either Stacks or Trimmomatic. The script will handle either single-end \
or paired-end reads appropriately. User must input the raw reads (unzipped fastq format) and a sample \
sheet (example is included as part of this repository). The script also includes the flexibility of \
running certain portions of the pipeline, which is useful if one doesn't need to repeat a specific step. \
The pipeline steps are as follows (with numbers corresponding to those passed using the -x flag):
1. Setup the environment - creates necessary directories.
2. Clone filtering - filters out PCR clones
3. Lead trimming - trims away 8bp UMI sequences
4. Sample parsing - parses sample sheet, creates barcode input, parses processed reads down to sample \
using this information, and renames the files logically using the sample sheet.
5. Quality filtering - quality filters the reads using Trimmomatic. If user specifies read quality \
filtering in Stacks, this filtering takes place simulteneously with read parsing (step 4).

Dependencies include the Stacks pipeline (v. 1.10 - 1.19), the FastX toolkit, and Trimmomatic v. 0.32 \
(if desired), and all need to be installed in the users path.

python process_rawreads.py -t <#threads> -s <samplesheet.txt> [-p -r] -c/-q -1 <single-end.fastq> \
[-2 <paired-end.fastq>] --renz1 <RE_1> --renz2 <RE_2> --bar_loc <inline/index> [-x [1,2,3,4,5]							
"""

#################################################
###           Parse command options           ###
#################################################

usage = usage_line
                        
parser = optparse.OptionParser(usage=usage)
parser.add_option("-t", action="store", type = "string", dest = "threads", help = "threads")
parser.add_option("-s", action="store", type = "string", dest = "sheet", help = "Sample sheet file (see sample)")
parser.add_option("-p", action="store_true", dest = "paired", help = "paired reads flag")
parser.add_option("-c", action="store_true", dest = "clean", help = "quality trim reads using Stacks")
parser.add_option("-q", action="store_true", dest = "quality", help = "quality trim reads using Trimmomatic")
parser.add_option("-r", action="store_true", dest = "rescue", help = "rescue barcodes/restriction sites in Stacks (default settings)")
parser.add_option("-1", action="store", type = "string", dest = "read1", help = "single end read")
parser.add_option("-2", action="store", type = "string", dest = "read2", help = "paired end read")
parser.add_option("--renz1", action="store", type = "string", dest = "renz1", help = "restriction enzyme 1 (common cutter)")
parser.add_option("--renz2", action="store", type = "string", dest = "renz2", help = "restriction enzyme 2 (rare cutter)")
parser.add_option("--bar_loc", action="store", type = "string", dest = "bar_loc", help = "location of barcode & index (per process_radtags documentation)")
parser.add_option("-x", action="store", type = "string", dest = "run", help = "processes to run, separated by commas (e.g., 1,2,...,5) [1,2,3,4,5]", default = "1,2,3,4,5")

options, args = parser.parse_args()


#################################################
###           Setup the environment           ###
#################################################

def setup(r1nm):
	print "\n***Setting up the command environment***\n"
### Create output directories ###
	os.system("mkdir clone_filtered")
	os.system("mkdir lead_trimmed")
	os.system("mkdir parsed")
	os.system("mkdir cleaned")
	os.system("mkdir ./parsed/"+r1nm)


#################################################
###             Clone filter reads            ###
#################################################

def PE_clone_filter():
	print "\n***Filtering PCR duplicates***\n"
	os.system("clone_filter -1 "+options.read1+" -2 "+options.read2+" -o ./clone_filtered/ 2>&1 | tee ./clone_filtered/"+options.read1+".clonefilter.log")

def SE_clone_filter():
	print "\n***Filtering PCR duplicates***\n"
	os.system("clone_filter -1 "+options.read1+" -2 "+options.read1+" -o ./clone_filtered/ 2>&1 | tee ./clone_filtered/"+options.read1+".clonefilter.log")
	os.system("rm -f ./clone_filtered/*.fil.fq_2")

#################################################
###             Trim leading 8bp UMI          ###
#################################################

def PE_lead_trim(r1nm, r2nm):
	print "\n***Trimming away leading 8bp unique molecular identifiers***\n"
	os.system("fastx_trimmer -Q 33 -f 9 -i ./clone_filtered/"+r1nm+".fil.fq_1 -o ./lead_trimmed/"+r1nm+".1.clone.trim.fastq")
	os.system("fastx_trimmer -Q 33 -f 9 -i ./clone_filtered/"+r2nm+".fil.fq_2 -o ./lead_trimmed/"+r2nm+".2.clone.trim.fastq")

def SE_lead_trim(r1nm):
	print "\n***Trimming away leading 8bp unique molecular identifiers***\n"
	os.system("fastx_trimmer -Q 33 -f 9 -i ./clone_filtered/"+r1nm+".fil.fq_1 -o ./lead_trimmed/"+r1nm+".1.clone.trim.fastq")

			
#################################################
###               Parse samples               ###
#################################################

def parse_sample_sheet():
	print "\n***Parsing reads by sample***\n"

### Parse the sample sheet to create barcodes file ###
	barcodes = open("barcodes.txt", "w")
	for line in open(options.sheet, "r"):
		if not line.strip().startswith("#"):
			bar = line.rstrip().split("\t")
			if options.paired == True:
#				print bar[0], bar[1], bar[2], bar[3], bar[4]
        			out = bar[3] + "\t" + bar[4] + "\n"
#				print out
        			barcodes.write(out)
			else:
				out = bar[3] + "\n"
				barcodes.write(out)
	barcodes.close()

### process_radtags subroutine ###
def PE_sample_parser(r1nm, r2nm):
	if options.rescue == True:
		if options.clean == True:
			alert = open("./cleaned/ATTENTION", "w")
			line = "You elected to quality-trim your reads using Stacks. This trimming was done simultaneously with parsing. See the 'parsed' folder for your trimmed reads."
			alert.write(line)
			alert.close()
			os.system("process_radtags -r -c -q -b barcodes.txt -o ./parsed/"+str(r1nm)+" --inline_index --renz_1 "+str(options.renz1)+" --renz_2 "+str(options.renz2)+" -1 ./lead_trimmed/"+str(r1nm)+".1.clone.trim.fastq -2 ./lead_trimmed/"+r2nm+".2.clone.trim.fastq 2>&1 | tee ./parsed/"+str(r1nm)+"/"+str(r1nm)+".parse.log")
			print "\n***Quality-trimming reads using Stacks***\n"
                        
		else:
			os.system("process_radtags -r -b barcodes.txt -o ./parsed/"+str(r1nm)+" --inline_index --renz_1 "+str(options.renz1)+" --renz_2 "+str(options.renz2)+" -1 ./lead_trimmed/"+str(r1nm)+".1.clone.trim.fastq -2 ./lead_trimmed/"+r2nm+".2.clone.trim.fastq 2>&1 | tee ./parsed/"+str(r1nm)+"/"+str(r1nm)+".parse.log")
			print "\n***Quality-trimming reads using Trimmomatic***\n"
	else:
		if options.clean == True:
        		os.system("process_radtags -c -q -b barcodes.txt -o ./parsed/"+str(r1nm)+" --inline_index --renz_1 "+str(options.renz1)+" --renz_2 "+str(options.renz2)+" -1 ./lead_trimmed/"+str(r1nm)+".1.clone.trim.fastq -2 ./lead_trimmed/"+r2nm+".2.clone.trim.fastq 2>&1 | tee ./parsed/"+str(r1nm)+"/"+str(r1nm)+".parse.log")
            		print "\n***Quality-trimming reads using Stacks***\n"
            		alert = open("./cleaned/ATTENTION", "w")
            		line = "You elected to quality-trim your reads using Stacks. This trimming was done simultaneously with parsing. See the 'parsed' folder for your trimmed reads."
            		alert.write(line)
            		alert.close()                   
		else:
			os.system("process_radtags -b barcodes.txt -o ./parsed/"+str(r1nm)+" --inline_index --renz_1 "+str(options.renz1)+" --renz_2 "+str(options.renz2)+" -1 ./lead_trimmed/"+str(r1nm)+".1.clone.trim.fastq -2 ./lead_trimmed/"+r2nm+".2.clone.trim.fastq 2>&1 | tee ./parsed/"+str(r1nm)+"/"+str(r1nm)+".parse.log")
            		print "\n***Quality-trimming reads using Trimmomatic***\n"
                                    

def SE_sample_parser(r1nm):
	if options.rescue == True:
		if options.clean == True:
			alert = open("./cleaned/ATTENTION", "w")
			line = "You elected to quality-trim your reads using Stacks. This trimming was done simultaneously with parsing. See the 'parsed' folder for your trimmed reads."
			alert.write(line)
			alert.close()
			os.system("process_radtags -r -c -q -b barcodes.txt -o ./parsed/"+str(r1nm)+" --inline_null --renz_1 "+str(options.renz1)+" --renz_2 "+str(options.renz2)+" -f ./lead_trimmed/"+str(r1nm)+".1.clone.trim.fastq 2>&1 | tee ./parsed/"+str(r1nm)+"/"+str(r1nm)+".parse.log")
			print "\n***Quality-trimming reads using Stacks***\n"
			                        
		else:
			os.system("process_radtags -r -b barcodes.txt -o ./parsed/"+str(r1nm)+" --inline_null --renz_1 "+str(options.renz1)+" --renz_2 "+str(options.renz2)+" -f ./lead_trimmed/"+str(r1nm)+".1.clone.trim.fastq 2>&1 | tee ./parsed/"+str(r1nm)+"/"+str(r1nm)+".parse.log")
			print "\n***Quality-trimming reads using Trimmomatic***\n"
	else:
        	if options.clean == True:
            		alert = open("./cleaned/ATTENTION", "w")
            		line = "You elected to quality-trim your reads using Stacks. This trimming was done simultaneously with parsing. See the 'parsed' folder for your trimmed reads."
            		alert.write(line)
            		alert.close()
			os.system("process_radtags -c -q -b barcodes.txt -o ./parsed/"+str(r1nm)+" --inline_null --renz_1 "+str(options.renz1)+" --renz_2 "+str(options.renz2)+" -f ./lead_trimmed/"+str(r1nm)+".1.clone.trim.fastq 2>&1 | tee ./parsed/"+str(r1nm)+"/"+str(r1nm)+".parse.log")
            		print "\n***Quality-trimming reads using Stacks***\n"
		else:
			os.system("process_radtags -b barcodes.txt -o ./parsed/"+str(r1nm)+" --inline_null --renz_1 "+str(options.renz1)+" --renz_2 "+str(options.renz2)+" -f ./lead_trimmed/"+str(r1nm)+".1.clone.trim.fastq 2>&1 | tee ./parsed/"+str(r1nm)+"/"+str(r1nm)+".parse.log")
            		print "\n***Quality-trimming reads using Trimmomatic***\n"                        


### file renaming subroutine ###
def PE_sample_rename(r1nm):
	for foo in open(options.sheet).read().splitlines():
        	bar = foo.split()
		parsep1_rename = "mv ./parsed/"+str(r1nm)+"/sample_"+bar[3]+"-"+bar[4]+".1.fq ./parsed/"+str(r1nm)+"/"+bar[0]+"_"+bar[3]+"-"+bar[4]+".P1.fq"
		parsep2_rename = "mv ./parsed/"+str(r1nm)+"/sample_"+bar[3]+"-"+bar[4]+".2.fq ./parsed/"+str(r1nm)+"/"+bar[0]+"_"+bar[3]+"-"+bar[4]+".P2.fq"
		remp1_rename = "mv ./parsed/"+str(r1nm)+"/sample_"+bar[3]+"-"+bar[4]+".rem.1.fq ./parsed/"+str(r1nm)+"/"+bar[0]+"_"+bar[3]+"-"+bar[4]+".rem.P1.fq"
		remp2_rename = "mv ./parsed/"+str(r1nm)+"/sample_"+bar[3]+"-"+bar[4]+".rem.2.fq ./parsed/"+str(r1nm)+"/"+bar[0]+"_"+bar[3]+"-"+bar[4]+".rem.P2.fq"
		combine_broken = "cat ./parsed/"+str(r1nm)+"/"+bar[0]+"_"+bar[3]+"-"+bar[4]+".rem.P1.fq /parsed/"+str(r1nm)+"/"+bar[0]+"_"+bar[3]+"-"+bar[4]+".rem.P2.fq > /parsed/"+str(r1nm)+"/"+bar[0]+"_"+bar[3]+"-"+bar[4]+".rem.cat.fq"
		os.system(parsep1_rename)
		os.system(parsep2_rename)
		os.system(remp1_rename)
		os.system(remp2_rename)
		os.system(combine_broken)
		
### Place restriction site trimming routine here ###

def SE_sample_rename(r1nm):
	for foo in open(options.sheet).read().splitlines():
        	bar = foo.split()
        	parse_single = "mv ./parsed/"+str(r1nm)+"/sample_"+bar[3]+".fq ./parsed/"+str(r1nm)+"/"+bar[0]+"_"+bar[3]+".S1.fq"
		os.system(parse_single)
### Place restriction site trimming routine here ###


#################################################
###     	Quality-trim samples	      ###
#################################################

def PE_quality_trim(r1nm):
	if options.quality == True:
		for foo in open(options.sheet).read().splitlines():
        		bar = foo.split()
			handle = bar[0]+"_"+bar[3]+"-"+bar[4]
			threads = options.threads
			PEclean = "trimmomatic-0.35.jar PE -threads "+threads+" -trimlog ./cleaned/"+handle+"_paired.qtrim.log ./parsed/"+str(r1nm)+"/"+handle+".P1.fq ./parsed/"+str(r1nm)+"/"+handle+".P2.fq ./cleaned/"+handle+".P1.qtrim ./cleaned/"+handle+".S1.qtrim ./cleaned/"+handle+".P2.qtrim ./cleaned/"+handle+".S2.qtrim LEADING:10 TRAILING:10 SLIDINGWINDOW:4:15 MINLEN:36 TOPHRED33 2>&1 | tee ./cleaned/"+handle+"_paired.qtrim.summary.log"
			broken_clean = "trimmomatic-0.35.jar SE -threads "+threads+" -trimlog ./cleaned/"+handle+"_broken.qtrim.log ./parsed/"+str(r1nm)+"/"+handle+".rem.cat.fq ./cleaned/"+handle+".broken.qtrim LEADING:10 TRAILING:10 SLIDINGWINDOW:4:15 MINLEN:36 TOPHRED33 2>&1 | tee ./cleaned/"+handle+".broken.qtrim.summary.log"
			os.system(str(PEclean))
			os.system(str(broken_clean))
			os.system("sed -i 's/\_1$/\ 1/g' ./cleaned/"+handle+".P1.qtrim")
			os.system("sed -i 's/\_2$/\ 2/g' ./cleaned/"+handle+".P2.qtrim")
			os.system("sed -i 's/\_1$/\ 1/g' ./cleaned/"+handle+".S1.qtrim")
                        os.system("sed -i 's/\_2$/\ 2/g' ./cleaned/"+handle+".S2.qtrim")
### Put command to trim away restriction site here and below else for Trimmomatic option ###
				
def SE_quality_trim(r1nm):
	if options.quality == True:
		for foo in open(options.sheet).read().splitlines():
        		bar = foo.split()
            		handle = bar[0]+"_"+bar[3]
            		threads = options.threads
            		SEclean = "trimmomatic-0.35.jar SE -threads "+threads+" -trimlog ./cleaned/"+handle+".qtrim.log ./parsed/"+str(r1nm)+"/"+handle+".S1.fq ./cleaned/"+handle+".S1.qtrim LEADING:10 TRAILING:10 SLIDINGWINDOW:4:15 MINLEN:36 TOPHRED33 2>&1 | tee ./cleaned/"+handle+".qtrim.summary.log"
			os.system(str(SEclean))
			os.system("sed -i 's/\_1$/\ 1/g' ./cleaned/"+handle+".S1.qtrim")
			os.system("sed -i 's/\_2$/\ 2/g' ./cleaned/"+handle+".S2.qtrim")
### Put command to trim away restriction site here and below else for Trimmomatic option ###



#################################################
###				Specify processes		      ###
#################################################	

def main():
	if options.paired == True:
		r1nm, r1ext = os.path.splitext(options.read1)
		r2nm, r2ext = os.path.splitext(options.read2)
		if "1" in options.run:
			setup(r1nm)
		if "2" in options.run:
			PE_clone_filter()
		if "3" in options.run:
			PE_lead_trim(r1nm, r2nm)
		if "4" in options.run:
			parse_sample_sheet()
			PE_sample_parser(r1nm, r2nm)
			PE_sample_rename(r1nm)
		if "5" in options.run:
			PE_quality_trim(r1nm)

	else:
		r1nm, r1ext = os.path.splitext(options.read1)
		if "1" in options.run:
			setup(r1nm)
		if "2" in options.run:
			SE_clone_filter()
		if "3" in options.run:
			SE_lead_trim(r1nm)
		if "4" in options.run:
			parse_sample_sheet()
			SE_sample_parser(r1nm)
			SE_sample_rename(r1nm)
		if "5" in options.run:
			SE_quality_trim(r1nm)

main()
