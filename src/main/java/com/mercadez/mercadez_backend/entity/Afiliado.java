package com.mercadez.mercadez_backend.entity;

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "afiliados")
public class Afiliado {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String nome_proprietario;
    private String email;
    private String cnpj;
    private String endereco;
    private String telefone;
    private String mercado;
    private String categoria;
    private Integer funcionarios;
    private String pagamento;
    private String senha;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getNome_proprietario() { return nome_proprietario; }
    public void setNome_proprietario(String nome_proprietario) {
        this.nome_proprietario = nome_proprietario;
    }

    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }

    public String getCnpj() { return cnpj; }
    public void setCnpj(String cnpj) { this.cnpj = cnpj; }

    public String getEndereco() { return endereco; }
    public void setEndereco(String endereco) { this.endereco = endereco; }

    public String getTelefone() { return telefone; }
    public void setTelefone(String telefone) { this.telefone = telefone; }

    public String getMercado() { return mercado; }
    public void setMercado(String mercado) { this.mercado = mercado; }

    public String getCategoria() { return categoria; }
    public void setCategoria(String categoria) { this.categoria = categoria; }

    public Integer getFuncionarios() { return funcionarios; }
    public void setFuncionarios(Integer funcionarios) {
        this.funcionarios = funcionarios;
    }

    public String getPagamento() { return pagamento; }
    public void setPagamento(String pagamento) { this.pagamento = pagamento; }

    public String getSenha() { return senha; }
    public void setSenha(String senha) { this.senha = senha; }
}
