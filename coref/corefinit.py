#!/usr/bin/env python3

# This library is under the 3-Clause BSD License
#
# Copyright (c) 2022-2023,  Orange
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
# 
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
# 
#    * Neither the name of Orange nor the
#      names of its contributors may be used to endorse or promote products
#      derived from this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL ORANGE BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# SPDX-License-Identifier: BSD-3-Clause
# Software Name: MetAMoRphosED AMR-Editor
# Author: Johannes Heinecke


import os
import sys
import json
import collections
import pathlib
parent = pathlib.Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(parent))

import penman
import amrdoc


class CorefInit:
    def __init__(self, sids, files, outbase, startid):
        self.sidpatterns = sids
        self.amrdocs = []
        self.sids = {} # sidpattern : collections.OrderedDict(){ sid: filename }

        for sp in self.sidpatterns:
            self.sids[sp] = collections.OrderedDict()

        self.sentences = {} # sid: AMRsentence
            
        for fn in files:
            fn = os.path.abspath(fn)
            ad = amrdoc.AMRdoc(fn)
            self.amrdocs.append(ad)

            for sid in ad.ids:
                # for all sentid in the document
                for spat in self.sidpatterns:
                    if sid.startswith(spat):
                        self.sids[spat][sid] = fn #,ad.ids[sid]
                        self.sentences[sid] = ad.ids[sid]
                        break
        

        for j, sp in enumerate(self.sids, 1):
            if len(self.sids[sp]) == 0:
                print("no sentences found for %s" % sp)
                continue
            if outbase == "-":
                ofpxml = open("%s.xml" % (sp), "w")
            elif "%" in outbase:
                ofpxml = open(outbase % (j+startid-1), "w")
            else:
                ofpxml = open("%s_%03d.xml" % (outbase, j), "w")
            id_file = []
            print('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE msamr SYSTEM "msamr.dtd">\n<document>', file=ofpxml)
            print('  <comment>generated by corefinit.py --startid %d -o %s -a %s --sids %s</comment>' % (j+startid-1, outbase, " ".join(files), sp), file=ofpxml)
            print('   <sentences annotator="" docid="%s" end="" site="" sourcetype="" start="" threadid="">' % sp, file=ofpxml)
            for i, sid in enumerate(self.sids[sp], 1):
                print('    <amr id="%s" order="%s" post="p1" speaker="unk" su="%s"/>' % (sid, i, i), file=ofpxml)
                id_file.append({"id": sid, "file": self.sids[sp][sid]})
            print('   </sentences>', file=ofpxml)
            print('   <relations>', file=ofpxml)
            self.createwikichains(sp, ofpxml)
            print('      <singletons/>', file=ofpxml)
            print('      <bridging/>', file=ofpxml)
            print('   </relations>', file=ofpxml)
            print('</document>', file=ofpxml)
            ofpxml.close()

            #ofpjson = open("%s_%03d.json" % (outbase, j), "w")
            #json.dump(id_file, ofpjson, indent=2)
            #ofpjson.close()

    def createwikichains(self, sp, ofp=sys.stdout):
        # add coreference chains for named entities using :wiki relations
        # and dates
        chains = {} # wiki-o: [(sid,var,concept)], y-m-d: [(sid,var,concept)]
        for i, sid in enumerate(self.sids[sp]):
            datevars = {} # var: {month:, day:, year:}
            names1 = set() # vars having a name and an empty wiki
            names2 = {} # person-var: name:var
            names = {} # var: "op1 op2 op3"
            #print(i, sid)
            sent = self.sentences[sid]
            #print(sent.amr)
            g = penman.decode(sent.amr)
            #print(g.attributes())
            concepts = {} # var: concept
            for s,p,o in g.instances():
                concepts[s] = o
                if o == "date-entity":
                    datevars[s] = {}


            for s,p,o in g.attributes():
                if p == ":wiki":
                    if o != "-":
                        o = o.replace('"', '')
                        if not o in chains:
                            chains[o] = []
                        chains[o].append((sid, s, concepts[s]))
                    else:
                        # person/city without wiki link
                        names1.add(s)
                elif p.startswith(":op"):
                    if not s in names:
                        names[s] = {}
                    names[s][p] = o
                elif s in datevars:
                    datevars[s][p] = o
            for s,p,o in g.edges():
                if p == ":name":
                    names2[s] = o

            #print("\nXXX", sid, names1)
            #print("YYY", sid, names2)
            #print("ZZZ", sid, names)
            for k in datevars:
                if ":time" in datevars[k] or ":timezone" in datevars[k]:
                    continue
                # get date as string yyyy-mm-dd
                datestring = "-".join(["%02d" % int(x[1]) for x in sorted(datevars[k].items(), reverse=True)])
                if not datestring in chains:
                    chains[datestring] = []
                chains[datestring].append((sid, k, "date-entity"))
            for p in names1:
                # get date as string yyyy-mm-dd
                n = names2[p]
                namestring = " ".join([x[1].replace('"', '') for x in sorted(names[n].items())])
                if not namestring in chains:
                    chains[namestring] = []
                chains[namestring].append((sid, p, concepts[s]))
                #print("namestring", namestring , sid, p, concepts[s])
                

        print('      <identity>', file=ofp)
        for cid, c in enumerate(chains, 1):
            # print(c, chains[c])
            if len(chains[c]) > 1:
                print('        <identchain relationid="rel-%d">' % cid, file=ofp)
                for sid, var, concept in chains[c]:
                    print('            <mention concept="%s" id="%s" variable="%s">%s</mention>' % (concept, sid, var, c), file=ofp)
                print('        </identchain>', file=ofp)
        print('      </identity>', file=ofp)



if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--sids", "-s", nargs="+", required=True, type=str, help="list of sentence ids (without final .nn)")
    parser.add_argument("--outbase", "-o", default="-", type=str, help="prefix of output files (.xml and .json) if -, sid is used as output filename, if it contains %%03d, it will be used as a template. to start with other number than 1, use --startid")
    parser.add_argument("--startid", default=1, type=int, help="count files with template given with --outbase")
    parser.add_argument("--amrfiles", "-a", nargs="+", help="AMR files which contain the indicated files")

    if len(sys.argv) < 2:
        parser.print_help()
    else:
        args = parser.parse_args()
        ci = CorefInit(args.sids, args.amrfiles, args.outbase, args.startid)
