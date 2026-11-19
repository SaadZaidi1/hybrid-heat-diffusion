#include <mpi.h>
#include <omp.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

static std::uint64_t available_memory() {
#ifdef _WIN32
    MEMORYSTATUSEX info{}; info.dwLength=sizeof(info);
    return GlobalMemoryStatusEx(&info) ? info.ullAvailPhys : 0;
#else
    long pages=sysconf(_SC_AVPHYS_PAGES), page_size=sysconf(_SC_PAGESIZE);
    return pages>0 && page_size>0 ? std::uint64_t(pages)*page_size : 0;
#endif
}

struct Options {
    int n=2048, steps=1000, threads=1, tile=64;
    double alpha=1.0, dx=1.0, dt=-1.0, boundary=0.0;
    std::uint64_t seed=42;
    std::string mode="hybrid_overlap", init="hotspots", output="json", dump="";
    bool verify=false, local_init=false;
};

static Options parse(int argc, char** argv) {
    Options o;
    for (int i=1;i<argc;++i) {
        std::string a=argv[i];
        if(a=="--verify" || a=="--local-init") { if(a=="--verify") o.verify=true; else o.local_init=true; continue; }
        if(i+1>=argc) throw std::runtime_error("missing value for "+a);
        std::string v=argv[++i];
        if(a=="--size") o.n=std::stoi(v); else if(a=="--steps") o.steps=std::stoi(v);
        else if(a=="--threads") o.threads=std::stoi(v); else if(a=="--tile") o.tile=std::stoi(v);
        else if(a=="--alpha") o.alpha=std::stod(v); else if(a=="--dx") o.dx=std::stod(v);
        else if(a=="--dt") o.dt=std::stod(v); else if(a=="--boundary") o.boundary=std::stod(v);
        else if(a=="--seed") o.seed=std::stoull(v); else if(a=="--mode") o.mode=v;
        else if(a=="--init") o.init=v; else if(a=="--output") o.output=v;
        else if(a=="--dump") o.dump=v; else throw std::runtime_error("unknown option "+a);
    }
    if(o.n<3 || o.steps<0 || o.threads<1 || o.tile<1 || o.alpha<=0 || o.dx<=0 || o.dt==0 ||
       (o.init!="hotspots" && o.init!="random" && o.init!="sine") || (o.output!="json" && o.output!="csv-line"))
        throw std::runtime_error("invalid parameter");
    if(o.dt<0) o.dt=.9*o.dx*o.dx/(4*o.alpha);
    if(o.dt>o.dx*o.dx/(4*o.alpha)) throw std::runtime_error("unstable dt: exceeds dx^2/(4*alpha)");
    const std::vector<std::string> modes={"seq_naive","seq_tiled","omp","mpi","hybrid","hybrid_overlap"};
    if(std::find(modes.begin(),modes.end(),o.mode)==modes.end()) throw std::runtime_error("invalid mode");
    return o;
}

static std::uint64_t mix(std::uint64_t x) {
    x+=0x9e3779b97f4a7c15ULL; x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;
    x=(x^(x>>27))*0x94d049bb133111ebULL; return x^(x>>31);
}
static double initial(int y,int x,const Options& o) {
    if(y==0 || x==0 || y==o.n-1 || x==o.n-1) return o.boundary;
    if(o.init=="sine") return o.boundary+std::sin(std::acos(-1.0)*y/(o.n-1))*std::sin(std::acos(-1.0)*x/(o.n-1));
    if(o.init=="random") return 100.0*(mix(o.seed ^ (std::uint64_t(y)*std::uint64_t(o.n)+x))>>11)*0x1.0p-53;
    double a=double(y)/o.n-.33, b=double(x)/o.n-.33;
    double c=double(y)/o.n-.67, d=double(x)/o.n-.67;
    return 100*std::exp(-90*(a*a+b*b))+70*std::exp(-150*(c*c+d*d));
}
static void update(const double* a,double* b,int first,int last,int n,int global_start,double k,int tile,bool tiled,bool threaded) {
    if(tiled) {
        if(threaded) {
            #pragma omp parallel for collapse(2) schedule(static)
            for(int yy=first; yy<last; yy+=tile) for(int xx=1; xx<n-1; xx+=tile)
                for(int y=yy;y<std::min(yy+tile,last);++y) {
                    if(global_start+y-1==0 || global_start+y-1==n-1) continue;
                    #pragma omp simd
                    for(int x=xx;x<std::min(xx+tile,n-1);++x) {
                        auto p=std::size_t(y)*n+x;
                        b[p]=a[p]+k*(a[p-n]+a[p+n]+a[p-1]+a[p+1]-4*a[p]);
                    }
                }
        } else {
            for(int yy=first; yy<last; yy+=tile) for(int xx=1; xx<n-1; xx+=tile)
                for(int y=yy;y<std::min(yy+tile,last);++y) {
                    if(global_start+y-1==0 || global_start+y-1==n-1) continue;
                    for(int x=xx;x<std::min(xx+tile,n-1);++x) {
                        auto p=std::size_t(y)*n+x;
                        b[p]=a[p]+k*(a[p-n]+a[p+n]+a[p-1]+a[p+1]-4*a[p]);
                    }
                }
        }
    } else if(threaded) {
        #pragma omp parallel for schedule(static)
        for(int y=first;y<last;++y) {
            if(global_start+y-1==0 || global_start+y-1==n-1) continue;
            #pragma omp simd
            for(int x=1;x<n-1;++x) {
                auto p=std::size_t(y)*n+x;
                b[p]=a[p]+k*(a[p-n]+a[p+n]+a[p-1]+a[p+1]-4*a[p]);
            }
        }
    } else {
        for(int y=first;y<last;++y) {
            if(global_start+y-1==0 || global_start+y-1==n-1) continue;
            for(int x=1;x<n-1;++x) {
                auto p=std::size_t(y)*n+x;
                b[p]=a[p]+k*(a[p-n]+a[p+n]+a[p-1]+a[p+1]-4*a[p]);
            }
        }
    }
}
static void reference(std::vector<double>& g,const Options& o) {
    std::vector<double> next=g; const double k=o.alpha*o.dt/(o.dx*o.dx);
    for(int s=0;s<o.steps;++s) {
        for(int y=1;y<o.n-1;++y) for(int x=1;x<o.n-1;++x) {
            auto p=std::size_t(y)*o.n+x;
            next[p]=g[p]+k*(g[p-o.n]+g[p+o.n]+g[p-1]+g[p+1]-4*g[p]);
        }
        g.swap(next);
    }
}
int main(int argc,char** argv) {
    for(int i=1;i<argc;++i) if(std::string(argv[i])=="--help") {
        std::cout << "--size N --steps S --threads T --tile B --mode seq_naive|seq_tiled|omp|mpi|hybrid|hybrid_overlap --init hotspots|random|sine --seed K --alpha A --dx D --dt D --boundary T --local-init --verify --dump FILE --output json|csv-line\n";
        return 0;
    }
    int provided=0;
    MPI_Init_thread(&argc,&argv,MPI_THREAD_FUNNELED,&provided);
    int rank=0,size=1; MPI_Comm_rank(MPI_COMM_WORLD,&rank); MPI_Comm_size(MPI_COMM_WORLD,&size);
    int status=0;
    try {
        if(provided<MPI_THREAD_FUNNELED) throw std::runtime_error("MPI_THREAD_FUNNELED unavailable");
        Options o=parse(argc,argv);
        if(o.n<size) throw std::runtime_error("more ranks than grid rows");
        if(size>1 && (o.mode=="seq_naive" || o.mode=="seq_tiled" || o.mode=="omp")) throw std::runtime_error("selected mode requires one process");
        if(o.mode=="mpi" && o.threads!=1) throw std::runtime_error("mpi mode requires --threads 1");
        omp_set_dynamic(0); omp_set_num_threads(o.threads);
        const bool threaded=o.mode=="omp" || o.mode=="hybrid" || o.mode=="hybrid_overlap";
        const bool tiled=o.mode=="seq_tiled" || o.mode=="omp" || o.mode=="hybrid" || o.mode=="hybrid_overlap";
        int rows=o.n/size+(rank<o.n%size), start=rank*(o.n/size)+std::min(rank,o.n%size);
        const std::uint64_t cells=std::uint64_t(o.n)*o.n;
        if(cells>std::uint64_t(std::numeric_limits<int>::max())) throw std::runtime_error("grid exceeds MPI Scatterv/Gatherv int displacement limit");
        std::vector<int> counts(size),displs(size);
        for(int r=0;r<size;++r) { int rr=o.n/size+(r<o.n%size); int ss=r*(o.n/size)+std::min(r,o.n%size); counts[r]=rr*o.n; displs[r]=ss*o.n; }
        // Two local arrays plus optional root input/output; guard the largest allocation.
        std::uint64_t bytes=2ULL*(rows+2)*o.n*sizeof(double)+(rank==0 ? cells*sizeof(double)*(o.verify?2ULL:1ULL):0);
        std::uint64_t free_bytes=available_memory();
        if(bytes>8ULL*1024*1024*1024 || (free_bytes && bytes>free_bytes*3/4))
            throw std::runtime_error("estimated rank allocation exceeds safe available memory; use a smaller grid or more ranks");
        double t0=MPI_Wtime(), comm=0, comp=0;
        const std::size_t local_cells=std::size_t(rows+2)*o.n;
        std::unique_ptr<double[]> a(new double[local_cells]), b(new double[local_cells]);
        // First touch with the same row scheduling used in the compute phase.
        #pragma omp parallel for schedule(static) if(threaded)
        for(int y=0;y<rows+2;++y) for(int x=0;x<o.n;++x) { a[std::size_t(y)*o.n+x]=0; b[std::size_t(y)*o.n+x]=0; }
        std::vector<double> full;
        if(!o.local_init) {
            if(rank==0) { full.resize(cells); for(int y=0;y<o.n;++y) for(int x=0;x<o.n;++x) full[std::size_t(y)*o.n+x]=initial(y,x,o); }
            double c=MPI_Wtime();
            MPI_Scatterv(rank==0?full.data():nullptr,counts.data(),displs.data(),MPI_DOUBLE,a.get()+o.n,rows*o.n,MPI_DOUBLE,0,MPI_COMM_WORLD);
            comm+=MPI_Wtime()-c;
            full.clear(); full.shrink_to_fit();
        } else {
            #pragma omp parallel for schedule(static) if(threaded)
            for(int y=1;y<=rows;++y) for(int x=0;x<o.n;++x) a[std::size_t(y)*o.n+x]=initial(start+y-1,x,o);
        }
        std::copy(a.get()+o.n,a.get()+std::size_t(rows+1)*o.n,b.get()+o.n);
        double init_time=MPI_Wtime()-t0;
        const double k=o.alpha*o.dt/(o.dx*o.dx);
        const int up=rank==0?MPI_PROC_NULL:rank-1, down=rank==size-1?MPI_PROC_NULL:rank+1;
        double sample_local[3]={0,0,0}, sample_expected[3]={0,0,0};
        for(int step=0;step<o.steps;++step) {
            if(o.mode=="hybrid_overlap" && size>1) {
                MPI_Request req[4]; double c=MPI_Wtime();
                MPI_Irecv(a.get(),o.n,MPI_DOUBLE,up,11,MPI_COMM_WORLD,&req[0]);
                MPI_Irecv(a.get()+std::size_t(rows+1)*o.n,o.n,MPI_DOUBLE,down,10,MPI_COMM_WORLD,&req[1]);
                MPI_Isend(a.get()+o.n,o.n,MPI_DOUBLE,up,10,MPI_COMM_WORLD,&req[2]);
                MPI_Isend(a.get()+std::size_t(rows)*o.n,o.n,MPI_DOUBLE,down,11,MPI_COMM_WORLD,&req[3]);
                comm+=MPI_Wtime()-c;
                c=MPI_Wtime(); update(a.get(),b.get(),2,rows,o.n,start,k,o.tile,tiled,threaded); comp+=MPI_Wtime()-c;
                c=MPI_Wtime(); MPI_Waitall(4,req,MPI_STATUSES_IGNORE); comm+=MPI_Wtime()-c;
                c=MPI_Wtime(); update(a.get(),b.get(),1,2,o.n,start,k,o.tile,tiled,threaded);
                if(rows>1) update(a.get(),b.get(),rows,rows+1,o.n,start,k,o.tile,tiled,threaded);
                comp+=MPI_Wtime()-c;
            } else {
                if(size>1) {
                    double c=MPI_Wtime();
                    MPI_Sendrecv(a.get()+o.n,o.n,MPI_DOUBLE,up,10,a.get()+std::size_t(rows+1)*o.n,o.n,MPI_DOUBLE,down,10,MPI_COMM_WORLD,MPI_STATUS_IGNORE);
                    MPI_Sendrecv(a.get()+std::size_t(rows)*o.n,o.n,MPI_DOUBLE,down,11,a.get(),o.n,MPI_DOUBLE,up,11,MPI_COMM_WORLD,MPI_STATUS_IGNORE);
                    comm+=MPI_Wtime()-c;
                }
                double c=MPI_Wtime(); update(a.get(),b.get(),1,rows+1,o.n,start,k,o.tile,tiled,threaded); comp+=MPI_Wtime()-c;
            }
            if(step==o.steps-1) for(int q=0;q<3;++q) {
                int gy=std::clamp((q+1)*o.n/4,1,o.n-2), x=gy;
                if(gy>=start && gy<start+rows) {
                    int y=gy-start+1; auto p=std::size_t(y)*o.n+x;
                    sample_local[q]=a[p]+k*(a[p-o.n]+a[p+o.n]+a[p-1]+a[p+1]-4*a[p]);
                }
            }
            a.swap(b);
        }
        double c=MPI_Wtime();
        if(rank==0) full.resize(cells);
        MPI_Gatherv(a.get()+o.n,rows*o.n,MPI_DOUBLE,rank==0?full.data():nullptr,counts.data(),displs.data(),MPI_DOUBLE,0,MPI_COMM_WORLD);
        MPI_Reduce(sample_local,sample_expected,3,MPI_DOUBLE,MPI_SUM,0,MPI_COMM_WORLD);
        comm+=MPI_Wtime()-c;
        double elapsed=MPI_Wtime()-t0, timing[4]={init_time,comm,comp,elapsed}, maxima[4];
        MPI_Reduce(timing,maxima,4,MPI_DOUBLE,MPI_MAX,0,MPI_COMM_WORLD);
        if(rank==0) {
            double sum=0,mn=std::numeric_limits<double>::infinity(),mx=-mn;
            for(double v:full) { sum+=v; mn=std::min(mn,v); mx=std::max(mx,v); }
            double err=0, analytic_error=0, sample_error=0;
            if(o.steps>0) for(int q=0;q<3;++q) {
                int y=std::clamp((q+1)*o.n/4,1,o.n-2);
                sample_error=std::max(sample_error,std::abs(full[std::size_t(y)*o.n+y]-sample_expected[q]));
            }
            if(sample_error>1e-10) status=2;
            if(o.init=="sine") {
                double theta=std::acos(-1.0)/(o.n-1), factor=1+4*k*(std::cos(theta)-1);
                double amplitude=std::pow(factor,o.steps);
                for(int y=0;y<o.n;++y) for(int x=0;x<o.n;++x) {
                    double exact=o.boundary+amplitude*std::sin(theta*y)*std::sin(theta*x);
                    analytic_error=std::max(analytic_error,std::abs(full[std::size_t(y)*o.n+x]-exact));
                }
                if(analytic_error>1e-10) status=2;
            }
            if(o.verify) {
                std::vector<double> expected(cells);
                for(int y=0;y<o.n;++y) for(int x=0;x<o.n;++x) expected[std::size_t(y)*o.n+x]=initial(y,x,o);
                reference(expected,o);
                for(std::size_t i=0;i<cells;++i) err=std::max(err,std::abs(full[i]-expected[i])/(1+std::abs(expected[i])));
                if(err>1e-10) status=2;
            }
            if(!o.dump.empty()) {
                auto parent=std::filesystem::path(o.dump).parent_path();
                if(!parent.empty()) std::filesystem::create_directories(parent);
                std::ofstream out(o.dump); if(!out) throw std::runtime_error("cannot write dump");
                out<<"y,x,temperature\n"; int stride=std::max(1,o.n/256);
                for(int y=0;y<o.n;y+=stride) for(int x=0;x<o.n;x+=stride) out<<y<<','<<x<<','<<std::setprecision(17)<<full[std::size_t(y)*o.n+x]<<'\n';
            }
            double updates=double(o.n-2)*(o.n-2)*o.steps;
            std::cout<<std::setprecision(12);
            if(o.output=="json") std::cout<<"{\"mode\":\""<<o.mode<<"\",\"size\":"<<o.n<<",\"steps\":"<<o.steps<<",\"ranks\":"<<size<<",\"threads\":"<<o.threads<<",\"tile\":"<<o.tile<<",\"init_s\":"<<maxima[0]<<",\"comm_s\":"<<maxima[1]<<",\"compute_s\":"<<maxima[2]<<",\"total_s\":"<<maxima[3]<<",\"gflops\":"<<5*updates/maxima[3]/1e9<<",\"updates_per_s\":"<<updates/maxima[3]<<",\"sum\":"<<sum<<",\"mean\":"<<sum/cells<<",\"min\":"<<mn<<",\"max\":"<<mx<<",\"center\":"<<full[std::size_t(o.n/2)*o.n+o.n/2]<<",\"sample_error\":"<<sample_error<<",\"verify_error\":"<<err<<",\"analytic_error\":"<<analytic_error<<",\"verified\":"<<(o.verify?(status==0?"true":"false"):"null")<<"}\n";
            else std::cout<<o.mode<<','<<o.n<<','<<o.steps<<','<<size<<','<<o.threads<<','<<o.tile<<','<<maxima[0]<<','<<maxima[1]<<','<<maxima[2]<<','<<maxima[3]<<','<<5*updates/maxima[3]/1e9<<','<<updates/maxima[3]<<','<<sum<<','<<sum/cells<<','<<mn<<','<<mx<<','<<err<<'\n';
        }
        MPI_Bcast(&status,1,MPI_INT,0,MPI_COMM_WORLD);
    } catch(const std::exception& e) { std::cerr<<"rank "<<rank<<": "<<e.what()<<'\n'; MPI_Abort(MPI_COMM_WORLD,1); status=1; }
    MPI_Finalize(); return status;
}
