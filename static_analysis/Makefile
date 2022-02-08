DEBUG ?= true

all: traffic-rule-info.so

CXX = g++

ifeq ($(DEBUG), true)
	CXXFLAGS = -fPIC -std=c++11 $(shell llvm-config --cxxflags) -g -O0 -DDEBUG
else
	CXXFLAGS = -fPIC -std=c++11 $(shell llvm-config --cxxflags) -g -O0
endif

traffic-rule-info.so: traffic-rule-info.o reaching-definitions.o control-dependency.o dataflow.o utils.o
		$(CXX) -dylib -shared $(CXXFLAGS) $^ /usr/lib/libz3.a -o $@
clean:
		rm -f *.o *~ *.so
